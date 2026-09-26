<script setup lang="ts">
import { onMounted, ref } from "vue";

type HealthState = {
  status: string;
  service: string;
  mode: string;
  message: string;
};

const health = ref<HealthState | null>(null);
const healthError = ref("");

onMounted(async () => {
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
        <p>Local technical Video upload will appear here in the next slice.</p>
      </section>

      <section class="placeholder-block">
        <h2>Task list</h2>
        <p>No Videos yet. This area is reserved for local task management.</p>
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
        <ol>
          <li>ASR / transcript</li>
          <li>Segment scoring</li>
          <li>Selective Frame extraction</li>
          <li>VideoContext persistence</li>
          <li>Document and QA</li>
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
