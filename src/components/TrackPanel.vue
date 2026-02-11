<script setup>
import TrackCard from "./TrackCard.vue";

const props = defineProps({
  tracks: { type: Array, default: () => [] },
  processing: { type: Boolean, default: false },
});

const emit = defineEmits(["addTrack", "addFiles", "removeTrack", "removeClip", "importFiles"]);
</script>

<template>
  <div class="track-panel">
    <div class="panel-header">
      <h2 class="panel-title">Tracks</h2>
      <button
        class="btn btn-accent btn-sm"
        @click="emit('addTrack')"
        :disabled="processing"
      >
        + Track
      </button>
    </div>

    <!-- Empty state -->
    <div v-if="tracks.length === 0" class="empty-state">
      <div class="empty-icon">
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
        </svg>
      </div>
      <p class="empty-title">No tracks yet</p>
      <p class="empty-subtitle">
        Import audio/video files to get started. Files are auto-grouped by device name.
      </p>
      <button class="btn btn-primary" @click="emit('importFiles')">
        + Import Files
      </button>
      <p class="empty-hint">or drag &amp; drop files here</p>
    </div>

    <!-- Track list -->
    <TransitionGroup v-else name="list" tag="div" class="track-list">
      <TrackCard
        v-for="(track, index) in tracks"
        :key="track.name + '-' + index"
        :track="track"
        :index="index"
        :processing="processing"
        @addFiles="(i) => emit('addFiles', i)"
        @removeTrack="(i) => emit('removeTrack', i)"
        @removeClip="(ti, ci) => emit('removeClip', ti, ci)"
      />
    </TransitionGroup>
  </div>
</template>

<style scoped>
.track-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.panel-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-bright);
  letter-spacing: -0.3px;
}

.empty-state {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  padding: 32px 16px;
}

.empty-icon {
  color: var(--text-muted);
  margin-bottom: 16px;
  opacity: 0.5;
}

.empty-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-dim);
  margin-bottom: 6px;
}

.empty-subtitle {
  font-size: 12px;
  color: var(--text-muted);
  max-width: 220px;
  line-height: 1.5;
  margin-bottom: 20px;
}

.empty-hint {
  font-size: 11px;
  color: var(--text-muted);
  opacity: 0.5;
  margin-top: 10px;
}

.track-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
}
</style>
