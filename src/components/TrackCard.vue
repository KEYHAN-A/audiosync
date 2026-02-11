<script setup>
import { computed } from "vue";

const props = defineProps({
  track: { type: Object, required: true },
  index: { type: Number, required: true },
  processing: { type: Boolean, default: false },
});

const emit = defineEmits(["addFiles", "removeTrack", "removeClip"]);

const trackColors = [
  "#38bdf8", "#a78bfa", "#2dd4bf", "#fb7185",
  "#fbbf24", "#818cf8", "#34d399", "#e879f9",
];

const color = computed(() => trackColors[props.index % trackColors.length]);
const isAnalyzed = computed(() => props.track.clips?.some((c) => c.analyzed));

function formatDuration(seconds) {
  if (!seconds) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function formatOffset(seconds) {
  if (seconds === 0) return "+0.000s";
  return (seconds >= 0 ? "+" : "") + seconds.toFixed(3) + "s";
}

function confidenceClass(conf) {
  if (conf >= 5) return "conf-high";
  if (conf >= 3) return "conf-ok";
  return "conf-low";
}
</script>

<template>
  <div class="track-card" :style="{ '--track-color': color }">
    <div class="card-header">
      <div class="color-dot"></div>
      <span class="track-name">{{ track.name }}</span>
      <span v-if="track.is_reference" class="ref-badge">REF</span>
      <span class="clip-count">{{ track.clips?.length || 0 }} clips</span>

      <!-- Actions -->
      <button
        class="card-btn"
        title="Add files to track"
        @click="emit('addFiles', index)"
        :disabled="processing"
      >+</button>
      <button
        class="card-btn card-btn-danger"
        title="Remove track"
        @click="emit('removeTrack', index)"
        :disabled="processing"
      >&times;</button>
    </div>

    <!-- Empty track -->
    <div v-if="!track.clips?.length" class="card-empty">
      <p>Drop files here or click <strong>+</strong></p>
    </div>

    <!-- Clip list -->
    <div v-else class="clip-list">
      <div
        v-for="(clip, ci) in track.clips"
        :key="clip.file_path"
        class="clip-item"
      >
        <div class="clip-main">
          <span class="clip-icon" :class="{ video: clip.is_video }">
            {{ clip.is_video ? "V" : "A" }}
          </span>
          <span class="clip-name" :title="clip.file_path">{{ clip.name }}</span>
          <span class="clip-duration">{{ formatDuration(clip.duration_s) }}</span>
          <button
            class="clip-remove"
            title="Remove clip"
            @click="emit('removeClip', index, ci)"
            :disabled="processing"
          >&times;</button>
        </div>

        <!-- Analysis results (visible after analysis) -->
        <div v-if="clip.analyzed" class="clip-analysis">
          <span class="clip-offset">{{ formatOffset(clip.timeline_offset_s) }}</span>
          <span class="clip-conf" :class="confidenceClass(clip.confidence)">
            {{ clip.confidence.toFixed(1) }}
          </span>
          <span v-if="clip.drift_ppm && Math.abs(clip.drift_ppm) > 0.1" class="clip-drift">
            {{ clip.drift_ppm > 0 ? "+" : "" }}{{ clip.drift_ppm.toFixed(1) }}ppm
          </span>
          <span v-if="clip.drift_corrected" class="clip-drift-fixed" title="Drift corrected">
            DC
          </span>
        </div>
      </div>
    </div>

    <!-- Track summary (after analysis) -->
    <div v-if="isAnalyzed" class="card-summary">
      <span>{{ formatDuration(track.total_duration_s) }} total</span>
    </div>
  </div>
</template>

<style scoped>
.track-card {
  background: rgba(21, 28, 46, 0.6);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid rgba(56, 189, 248, 0.12);
  border-radius: 14px;
  padding: 14px;
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
}

.track-card:hover {
  border-color: rgba(56, 189, 248, 0.25);
  box-shadow: 0 0 24px rgba(56, 189, 248, 0.06);
  transform: translateY(-1px);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
}

.color-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  background-color: var(--track-color);
  box-shadow: 0 0 8px var(--track-color);
  flex-shrink: 0;
}

.track-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-bright);
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ref-badge {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.5px;
  padding: 2px 6px;
  border-radius: 6px;
  background: rgba(56, 189, 248, 0.15);
  color: var(--cyan);
}

.clip-count {
  font-size: 11px;
  color: var(--text-muted);
  flex-shrink: 0;
}

.card-btn {
  width: 22px;
  height: 22px;
  border: 1px solid var(--border-subtle);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.04);
  color: var(--text-muted);
  font-size: 14px;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s ease;
  padding: 0;
}

.card-btn:hover:not(:disabled) {
  background: rgba(56, 189, 248, 0.1);
  border-color: var(--cyan);
  color: var(--cyan);
}

.card-btn-danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.1);
  border-color: #ef4444;
  color: #ef4444;
}

.card-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.card-empty {
  padding: 12px 0;
  text-align: center;
}

.card-empty p {
  font-size: 11px;
  color: var(--text-muted);
}

.clip-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.clip-item {
  padding: 5px 8px;
  border-radius: 8px;
  background: rgba(255, 255, 255, 0.03);
  transition: background 0.15s ease;
}

.clip-item:hover {
  background: rgba(56, 189, 248, 0.06);
}

.clip-main {
  display: flex;
  align-items: center;
  gap: 6px;
}

.clip-icon {
  width: 18px;
  height: 18px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 9px;
  font-weight: 700;
  background: rgba(56, 189, 248, 0.12);
  color: var(--cyan);
  flex-shrink: 0;
}

.clip-icon.video {
  background: rgba(167, 139, 250, 0.12);
  color: var(--purple);
}

.clip-name {
  font-size: 11px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.clip-duration {
  font-size: 10px;
  font-family: "JetBrains Mono", "SF Mono", "Menlo", monospace;
  color: var(--text-dim);
  flex-shrink: 0;
}

.clip-remove {
  width: 16px;
  height: 16px;
  border: none;
  border-radius: 4px;
  background: transparent;
  color: var(--text-muted);
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  opacity: 0;
  transition: all 0.15s ease;
}

.clip-item:hover .clip-remove {
  opacity: 0.6;
}

.clip-remove:hover:not(:disabled) {
  opacity: 1;
  color: #ef4444;
  background: rgba(239, 68, 68, 0.1);
}

/* Analysis results row */
.clip-analysis {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 3px;
  padding-left: 24px;
  font-size: 10px;
  font-family: "JetBrains Mono", "SF Mono", "Menlo", monospace;
}

.clip-offset {
  color: var(--text-dim);
}

.clip-conf {
  padding: 1px 4px;
  border-radius: 4px;
  font-weight: 600;
}

.conf-high {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
}

.conf-ok {
  background: rgba(251, 191, 36, 0.15);
  color: #fbbf24;
}

.conf-low {
  background: rgba(239, 68, 68, 0.15);
  color: #fb7185;
}

.clip-drift {
  color: var(--text-muted);
}

.clip-drift-fixed {
  padding: 1px 4px;
  border-radius: 4px;
  background: rgba(56, 189, 248, 0.12);
  color: var(--cyan);
  font-size: 9px;
  font-weight: 700;
}

.card-summary {
  margin-top: 8px;
  padding-top: 8px;
  border-top: 1px solid var(--border-subtle);
  font-size: 10px;
  color: var(--text-muted);
  display: flex;
  justify-content: flex-end;
}
</style>
