<script setup>
import { ref, computed } from "vue";

const props = defineProps({
  visible: { type: Boolean, default: false },
  tracks: { type: Array, default: () => [] },
});

const emit = defineEmits(["close", "export"]);

const outputDir = ref("./audiosync_output");
const format = ref("wav");
const bitDepth = ref(24);
const driftCorrection = ref(true);
const exportFcpxml = ref(false);
const exportEdl = ref(false);

const formats = [
  { value: "wav", label: "WAV (Lossless)", desc: "Best quality, large files" },
  { value: "flac", label: "FLAC (Lossless)", desc: "Compressed, great quality" },
  { value: "aiff", label: "AIFF (Lossless)", desc: "Apple standard" },
  { value: "mp3", label: "MP3 (320 kbps)", desc: "Compact, lossy" },
];

const bitDepths = [
  { value: 16, label: "16-bit" },
  { value: 24, label: "24-bit" },
  { value: 32, label: "32-bit float" },
];

const isLossy = computed(() => format.value === "mp3");

function handleExport() {
  emit("export", {
    output_dir: outputDir.value,
    format: format.value,
    bit_depth: bitDepth.value,
    drift_correction: driftCorrection.value,
    fcpxml_path: exportFcpxml.value
      ? `${outputDir.value}/timeline.fcpxml`
      : null,
    edl_path: exportEdl.value
      ? `${outputDir.value}/timeline.edl`
      : null,
  });
}
</script>

<template>
  <Transition name="fade">
    <div v-if="visible" class="dialog-overlay" @click.self="emit('close')">
      <div class="dialog glass-card">
        <div class="dialog-header">
          <h3 class="dialog-title">Export Synced Audio</h3>
          <button class="close-btn" @click="emit('close')">&times;</button>
        </div>

        <div class="form-group">
          <label class="form-label">Output Directory</label>
          <input
            v-model="outputDir"
            class="form-input"
            type="text"
            placeholder="./audiosync_output"
          />
        </div>

        <div class="form-group">
          <label class="form-label">Format</label>
          <div class="format-grid">
            <label
              v-for="f in formats"
              :key="f.value"
              class="format-option"
              :class="{ selected: format === f.value }"
            >
              <input type="radio" :value="f.value" v-model="format" class="sr-only" />
              <span class="format-name">{{ f.label }}</span>
              <span class="format-desc">{{ f.desc }}</span>
            </label>
          </div>
        </div>

        <div v-if="!isLossy" class="form-group">
          <label class="form-label">Bit Depth</label>
          <div class="radio-group">
            <label
              v-for="bd in bitDepths"
              :key="bd.value"
              class="radio-option"
              :class="{ selected: bitDepth === bd.value }"
            >
              <input type="radio" :value="bd.value" v-model="bitDepth" class="sr-only" />
              <span>{{ bd.label }}</span>
            </label>
          </div>
        </div>

        <div class="form-group">
          <label class="toggle-row">
            <input type="checkbox" v-model="driftCorrection" />
            <span class="toggle-label">Automatic drift correction</span>
          </label>
        </div>

        <div class="form-group">
          <label class="form-label">Timeline Export</label>
          <div class="checkbox-group">
            <label class="toggle-row">
              <input type="checkbox" v-model="exportFcpxml" />
              <span class="toggle-label">FCPXML (Final Cut Pro / DaVinci Resolve)</span>
            </label>
            <label class="toggle-row">
              <input type="checkbox" v-model="exportEdl" />
              <span class="toggle-label">EDL (Premiere Pro / Avid)</span>
            </label>
          </div>
        </div>

        <div class="dialog-footer">
          <button class="btn btn-ghost" @click="emit('close')">Cancel</button>
          <button class="btn btn-primary" @click="handleExport">
            Export {{ tracks.length }} Tracks
          </button>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.dialog-overlay {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(6, 12, 28, 0.75);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.dialog {
  width: 500px;
  max-width: 90vw;
  max-height: 85vh;
  overflow-y: auto;
  padding: 28px;
  border-radius: 20px;
  background: rgba(21, 28, 46, 0.95);
  border: 1px solid rgba(56, 189, 248, 0.15);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.5);
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 24px;
}

.dialog-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-bright);
}

.close-btn {
  width: 28px;
  height: 28px;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  background: transparent;
  color: var(--text-muted);
  font-size: 16px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}

.close-btn:hover {
  background: rgba(239, 68, 68, 0.1);
  border-color: #ef4444;
  color: #ef4444;
}

.form-group {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 8px;
}

.form-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border-light);
  border-radius: 10px;
  background: var(--bg-input);
  color: var(--text);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s ease;
}

.form-input:focus {
  border-color: var(--cyan);
}

.format-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 8px;
}

.format-option {
  display: flex;
  flex-direction: column;
  padding: 10px 12px;
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s ease;
  background: rgba(255, 255, 255, 0.02);
}

.format-option:hover {
  border-color: var(--border-light);
  background: rgba(56, 189, 248, 0.04);
}

.format-option.selected {
  border-color: var(--cyan);
  background: rgba(56, 189, 248, 0.08);
  box-shadow: 0 0 12px var(--glow-cyan);
}

.format-name {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-bright);
  margin-bottom: 2px;
}

.format-desc {
  font-size: 10px;
  color: var(--text-muted);
}

.radio-group {
  display: flex;
  gap: 8px;
}

.radio-option {
  padding: 6px 14px;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  cursor: pointer;
  font-size: 12px;
  color: var(--text-dim);
  transition: all 0.2s ease;
}

.radio-option:hover {
  border-color: var(--border-light);
}

.radio-option.selected {
  border-color: var(--cyan);
  color: var(--cyan);
  background: rgba(56, 189, 248, 0.08);
}

.sr-only {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
}

.toggle-row {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
}

.toggle-row input[type="checkbox"] {
  width: 16px;
  height: 16px;
  accent-color: var(--cyan);
}

.toggle-label {
  font-size: 12px;
  color: var(--text);
}

.checkbox-group {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 24px;
  padding-top: 16px;
  border-top: 1px solid var(--border-subtle);
}
</style>
