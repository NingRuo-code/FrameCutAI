<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

type HealthState = {
  status: string;
  service: string;
  mode: string;
  message: string;
};

type VideoTask = {
  id: string;
  title: string;
  original_filename: string;
  content_type: string;
  file_size: number;
  status: string;
  created_at: string;
  updated_at: string;
};

type TaskEvent = {
  id: number;
  video_id: string;
  stage: string;
  level: string;
  message: string;
  created_at: string;
};

type SegmentScore = {
  source: string;
  technical_density: number;
  visual_dependency: number;
  operation_density: number;
  novelty: number;
  watch_value: number;
  confidence: number;
  reason: string;
};

type FrameContext = {
  frame_id: string;
  timestamp_seconds: number;
  image_path: string;
  ocr_text: string;
  visual_summary: string;
};

type SegmentContext = {
  segment_id: string;
  start_seconds: number;
  end_seconds: number;
  transcript_text: string;
  score: SegmentScore;
  selected_for_vision: boolean;
  frames: FrameContext[];
};

type EvidenceContext = {
  evidence_id: string;
  segment_id: string;
  start_seconds: number;
  end_seconds: number;
  summary: string;
  transcript_snippet: string;
  frame_ids: string[];
};

type ProviderCall = {
  id: number;
  provider: string;
  operation: string;
  latency_ms: number;
  input_units: number;
  output_units: number;
  estimated_cost_usd: number;
};

type VideoContextPayload = {
  stage: string;
  segments: SegmentContext[];
  evidence: EvidenceContext[];
};

type VideoContextResponse = {
  video_id: string;
  context: VideoContextPayload;
  provider_calls: ProviderCall[];
  updated_at: string;
};

const health = ref<HealthState | null>(null);
const healthError = ref("");
const videos = ref<VideoTask[]>([]);
const activeVideoId = ref("");
const taskEvents = ref<TaskEvent[]>([]);
const videoContext = ref<VideoContextResponse | null>(null);
const eventSource = ref<EventSource | null>(null);
const selectedFile = ref<File | null>(null);
const isUploading = ref(false);
const isAnalyzing = ref(false);
const taskError = ref("");
const taskNotice = ref("");
const contextError = ref("");

const hasVideos = computed(() => videos.value.length > 0);
const activeVideo = computed(
  () => videos.value.find((video) => video.id === activeVideoId.value) ?? null,
);
const contextSegments = computed(() => videoContext.value?.context.segments ?? []);
const contextEvidence = computed(() => videoContext.value?.context.evidence ?? []);
const providerCalls = computed(() => videoContext.value?.provider_calls ?? []);

async function loadHealth() {
  try {
    const response = await fetch("/api/health");
    if (!response.ok) {
      throw new Error(`Health check failed: ${response.status}`);
    }
    health.value = await response.json();
  } catch (error) {
    healthError.value =
      error instanceof Error ? error.message : "Unable to reach backend";
  }
}

async function loadVideos() {
  taskError.value = "";
  try {
    const response = await fetch("/api/videos");
    if (!response.ok) {
      throw new Error(`Could not load Videos: ${response.status}`);
    }
    videos.value = await response.json();
    if (!activeVideoId.value && videos.value.length > 0) {
      await selectVideo(videos.value[0]);
    }
  } catch (error) {
    taskError.value =
      error instanceof Error ? error.message : "Unable to load Videos";
  }
}

function onFileChange(event: Event) {
  const input = event.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] ?? null;
}

async function uploadVideo() {
  if (!selectedFile.value) {
    taskError.value = "Choose a local Video before uploading.";
    return;
  }

  taskError.value = "";
  taskNotice.value = "";
  isUploading.value = true;

  const formData = new FormData();
  formData.append("file", selectedFile.value);

  try {
    const response = await fetch("/api/videos", {
      method: "POST",
      body: formData,
    });
    if (!response.ok) {
      const errorBody = await response.json().catch(() => null);
      throw new Error(errorBody?.detail ?? `Upload failed: ${response.status}`);
    }
    const created: VideoTask = await response.json();
    taskNotice.value = `${created.original_filename} uploaded.`;
    selectedFile.value = null;
    await loadVideos();
    await selectVideo(created);
  } catch (error) {
    taskError.value =
      error instanceof Error ? error.message : "Unable to upload Video";
  } finally {
    isUploading.value = false;
  }
}

async function selectVideo(video: VideoTask) {
  activeVideoId.value = video.id;
  await Promise.all([loadEventHistory(video.id), loadVideoContext(video.id)]);
}

async function loadEventHistory(videoId = activeVideoId.value) {
  if (!videoId) {
    taskEvents.value = [];
    return;
  }

  try {
    const response = await fetch(`/api/videos/${videoId}/events/history`);
    if (!response.ok) {
      throw new Error(`Could not load events: ${response.status}`);
    }
    taskEvents.value = await response.json();
  } catch (error) {
    taskError.value =
      error instanceof Error ? error.message : "Unable to load Workflow events";
  }
}

function appendTaskEvent(event: TaskEvent) {
  if (taskEvents.value.some((existing) => existing.id === event.id)) {
    return;
  }
  taskEvents.value = [...taskEvents.value, event].sort((a, b) => a.id - b.id);
}

async function loadVideoContext(videoId = activeVideoId.value) {
  contextError.value = "";
  if (!videoId) {
    videoContext.value = null;
    return;
  }

  try {
    const response = await fetch(`/api/videos/${videoId}/context`);
    if (response.status === 404) {
      videoContext.value = null;
      return;
    }
    if (!response.ok) {
      throw new Error(`Could not load VideoContext: ${response.status}`);
    }
    videoContext.value = await response.json();
  } catch (error) {
    contextError.value =
      error instanceof Error ? error.message : "Unable to load VideoContext";
  }
}

function connectEventStream(videoId: string) {
  eventSource.value?.close();
  const source = new EventSource(`/api/videos/${videoId}/events`);
  eventSource.value = source;

  source.addEventListener("workflow_event", (message) => {
    const event = JSON.parse((message as MessageEvent).data) as TaskEvent;
    appendTaskEvent(event);
    if (event.message === "Mock Workflow completed.") {
      source.close();
      eventSource.value = null;
      void loadVideos();
      void loadVideoContext(videoId);
    }
  });

  source.onerror = () => {
    source.close();
    eventSource.value = null;
  };
}

async function startAnalysis(video: VideoTask) {
  taskError.value = "";
  taskNotice.value = "";
  isAnalyzing.value = true;
  await selectVideo(video);

  try {
    const response = await fetch(`/api/videos/${video.id}/analyze`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error(`Analyze failed: ${response.status}`);
    }
    taskNotice.value = `Mock Workflow queued for ${video.original_filename}.`;
    connectEventStream(video.id);
    await loadVideos();
    await loadVideoContext(video.id);
  } catch (error) {
    taskError.value =
      error instanceof Error ? error.message : "Unable to start Workflow";
  } finally {
    isAnalyzing.value = false;
  }
}

async function deleteVideo(video: VideoTask) {
  taskError.value = "";
  taskNotice.value = "";

  try {
    const response = await fetch(`/api/videos/${video.id}`, {
      method: "DELETE",
    });
    if (!response.ok) {
      throw new Error(`Delete failed: ${response.status}`);
    }
    taskNotice.value = `${video.original_filename} deleted.`;
    if (activeVideoId.value === video.id) {
      eventSource.value?.close();
      eventSource.value = null;
      activeVideoId.value = "";
      taskEvents.value = [];
      videoContext.value = null;
    }
    await loadVideos();
  } catch (error) {
    taskError.value =
      error instanceof Error ? error.message : "Unable to delete Video";
  }
}

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

onMounted(async () => {
  await Promise.all([loadHealth(), loadVideos()]);
});
</script>

<template>
  <main class="workspace-shell">
    <aside class="panel task-panel" aria-label="Task and upload area">
      <header>
        <p class="eyebrow">FrameCutAI</p>
        <h1>Video tasks</h1>
      </header>

      <section class="placeholder-block">
        <h2>Upload</h2>
        <form class="upload-form" @submit.prevent="uploadVideo">
          <input
            type="file"
            accept="video/mp4,video/quicktime,video/x-matroska,video/webm,video/x-msvideo,.mp4,.mov,.mkv,.webm,.avi"
            @change="onFileChange"
          />
          <button type="submit" :disabled="isUploading">
            {{ isUploading ? "Uploading..." : "Upload Video" }}
          </button>
        </form>
        <p class="hint-text">
          Accepted MVP formats: MP4, MOV, MKV, WebM, and AVI.
        </p>
      </section>

      <section class="placeholder-block">
        <div class="section-title-row">
          <h2>Task list</h2>
          <button class="secondary-button" type="button" @click="loadVideos">
            Refresh
          </button>
        </div>

        <p v-if="taskError" class="error-text">{{ taskError }}</p>
        <p v-if="taskNotice" class="success-text">{{ taskNotice }}</p>
        <p v-if="!hasVideos">No Videos yet. Upload a local technical Video.</p>

        <ul v-else class="video-list">
          <li
            v-for="video in videos"
            :key="video.id"
            class="video-list-item"
            :class="{ active: video.id === activeVideoId }"
          >
            <button class="video-summary-button" type="button" @click="selectVideo(video)">
              <strong>{{ video.title }}</strong>
              <span>{{ video.original_filename }}</span>
              <small>{{ video.status }} · {{ formatBytes(video.file_size) }}</small>
            </button>
            <div class="task-actions">
              <button
                type="button"
                class="secondary-button"
                :disabled="isAnalyzing"
                @click="startAnalysis(video)"
              >
                Analyze
              </button>
              <button type="button" class="danger-button" @click="deleteVideo(video)">
                Delete
              </button>
            </div>
          </li>
        </ul>
      </section>
    </aside>

    <section class="panel progress-panel" aria-label="Agent progress and debug">
      <header class="panel-header">
        <div>
          <p class="eyebrow">Workflow</p>
          <h2>Agent progress</h2>
        </div>
        <div class="health-pill" :class="{ offline: healthError }">
          <span>{{ health?.status ?? (healthError ? "error" : "checking") }}</span>
        </div>
      </header>

      <section class="status-card">
        <h3>Backend health</h3>
        <p v-if="health">
          {{ health.service }} is running in {{ health.mode }} mode.
          {{ health.message }}
        </p>
        <p v-else-if="healthError" class="error-text">{{ healthError }}</p>
        <p v-else>Checking local API...</p>
      </section>

      <section class="placeholder-block timeline">
        <h3>Stage timeline</h3>
        <p v-if="activeVideo">
          Showing persisted Workflow events for {{ activeVideo.original_filename }}.
        </p>
        <p v-else>Select or upload a Video to see Workflow events.</p>
        <ol v-if="taskEvents.length > 0" class="event-list">
          <li v-for="event in taskEvents" :key="event.id">
            <span>{{ event.stage }}</span>
            <strong>{{ event.message }}</strong>
          </li>
        </ol>
        <ol v-else class="event-list muted-events">
          <li><span>asr</span><strong>Waiting for mock Workflow</strong></li>
          <li><span>segmenting</span><strong>Waiting for mock Workflow</strong></li>
          <li><span>scoring</span><strong>Waiting for mock Workflow</strong></li>
          <li><span>vision</span><strong>Waiting for mock Workflow</strong></li>
          <li><span>document</span><strong>Waiting for mock Workflow</strong></li>
        </ol>
      </section>

      <section class="placeholder-block context-debug">
        <h3>VideoContext debug</h3>
        <p v-if="contextError" class="error-text">{{ contextError }}</p>
        <p v-else-if="!videoContext">
          Run analysis to inspect Segments, scores, Frames, Evidence, and Provider calls.
        </p>
        <template v-else>
          <div class="debug-summary">
            <span>{{ videoContext.context.stage }}</span>
            <span>{{ contextSegments.length }} Segments</span>
            <span>{{ providerCalls.length }} Provider calls</span>
          </div>

          <div class="debug-group">
            <h4>Segments</h4>
            <article
              v-for="segment in contextSegments"
              :key="segment.segment_id"
              class="debug-item"
            >
              <div class="debug-item-header">
                <strong>{{ segment.segment_id }}</strong>
                <span>{{ segment.start_seconds }}s-{{ segment.end_seconds }}s</span>
              </div>
              <p>{{ segment.transcript_text || "No transcript in this Segment." }}</p>
              <div class="score-grid">
                <span>score: {{ segment.score.source }}</span>
                <span>visual {{ segment.score.visual_dependency }}</span>
                <span>watch {{ segment.score.watch_value }}</span>
                <span>{{ segment.selected_for_vision ? "vision" : "asr-only" }}</span>
              </div>
              <ul v-if="segment.frames.length > 0" class="frame-list">
                <li v-for="frame in segment.frames" :key="frame.frame_id">
                  <strong>{{ frame.timestamp_seconds }}s</strong>
                  <span>{{ frame.ocr_text }}</span>
                  <small>{{ frame.visual_summary }}</small>
                </li>
              </ul>
            </article>
          </div>

          <div class="debug-group">
            <h4>Evidence</h4>
            <article
              v-for="item in contextEvidence"
              :key="item.evidence_id"
              class="debug-item"
            >
              <div class="debug-item-header">
                <strong>{{ item.segment_id }}</strong>
                <span>{{ item.start_seconds }}s-{{ item.end_seconds }}s</span>
              </div>
              <p>{{ item.summary }}</p>
              <small>Frames: {{ item.frame_ids.join(", ") || "none" }}</small>
            </article>
          </div>

          <div class="debug-group">
            <h4>Provider calls</h4>
            <article
              v-for="call in providerCalls"
              :key="call.id"
              class="debug-item provider-call"
            >
              <strong>{{ call.provider }}</strong>
              <span>{{ call.operation }}</span>
              <small>
                {{ call.latency_ms }}ms · in {{ call.input_units }} · out
                {{ call.output_units }} · ${{ call.estimated_cost_usd.toFixed(4) }}
              </small>
            </article>
          </div>
        </template>
      </section>
    </section>

    <section class="panel output-panel" aria-label="Document, player, and QA">
      <section class="placeholder-block player-shell">
        <h2>Source Video</h2>
        <div class="player-placeholder">Player timestamp jumps land here</div>
      </section>

      <section class="placeholder-block">
        <h2>Technical document</h2>
        <p>Traceable Markdown output and Evidence links will render here.</p>
      </section>

      <section class="placeholder-block qa-shell">
        <h2>Current-Video QA</h2>
        <p>Evidence-backed answers and refusal states will appear here.</p>
      </section>
    </section>
  </main>
</template>
