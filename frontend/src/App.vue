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

const health = ref<HealthState | null>(null);
const healthError = ref("");
const videos = ref<VideoTask[]>([]);
const activeVideoId = ref("");
const taskEvents = ref<TaskEvent[]>([]);
const eventSource = ref<EventSource | null>(null);
const selectedFile = ref<File | null>(null);
const isUploading = ref(false);
const isAnalyzing = ref(false);
const taskError = ref("");
const taskNotice = ref("");

const hasVideos = computed(() => videos.value.length > 0);
const activeVideo = computed(
  () => videos.value.find((video) => video.id === activeVideoId.value) ?? null,
);

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
  await loadEventHistory(video.id);
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

      <section class="placeholder-block">
        <h3>VideoContext debug</h3>
        <p>Segments, scores, Frames, and Evidence summaries will appear here.</p>
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
