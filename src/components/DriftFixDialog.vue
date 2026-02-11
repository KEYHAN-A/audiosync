<script setup>
import { ref, computed } from "vue";
import { useAudioSync } from "../composables/useAudioSync.js";
import { open } from "@tauri-apps/plugin-dialog";

const props = defineProps({
  visible: { type: Boolean, default: false },
});

const emit = defineEmits(["close"]);

const { measureDrift, state } = useAudioSync();

const referencePath = ref("");
const targetPath = ref("");
const result = ref(null);
const measuring = ref(false);

const refName = computed(() =>
  referencePath.value
    ? referencePath.value.split("/").pop().split("\\").pop()
    : "None selected"
);

const tgtName = computed(() =>
  targetPath.value
    ? targetPath.value.split("/").pop().split("\\").pop()
    : "None selected"
);

const canMeasure = computed(
  () => referencePath.value && targetPath.value && !measuring.value
);

const audioFilters = [
  {
    name: "Audio & Video",
    extensions: [
      "wav", "aiff", "aif", "flac", "mp3", "ogg", "opus",
      "mp4", "mov", "mkv", "avi", "webm", "mts", "m4v", "mxf",
    ],
  },
];

async function pickReference() {
  const selected = await open({
    title: "Select Reference File",
    multiple: false,
    filters: audioFilters,
  });
  if (selected) {
    referencePath.value = typeof selected === "string" ? selected : selected.path;
    result.value = null;
  }
}

async function pickTarget() {
  const selected = await open({
    title: "Select Target File",
    multiple: false,
    filters: audioFilters,
  });
  if (selected) {
    targetPath.value = typeof selected === "string" ? selected : selected.path;
    result.value = null;
  }
}

async function runMeasurement() {
  if (!canMeasure.value) return;
  measuring.value = true;
  result.value = null;

  try {
    const r = await measureDrift(referencePath.value, targetPath.value);
    result.value = r;
  } finally {
    measuring.value = false;
  }
}

function formatPpm(ppm) {
  return (ppm >= 0 ? "+" : "") + ppm.toFixed(2) + " ppm";
}

function close() {
  result.value = null;
  emit("close");
}
</script>

<template>
  <Transition name="scale">
    <div v-if="visible" class="dialog-overlay" @click.self="close">
      <div class="dialog">
        <div class="dialog-header">
          <h3 class="dialog-title">Drift Measurement</h3>
          <button class="close-btn" @click="close">&times;</button>
        </div>

        <p class="dialog-desc">
          Compare two recordings to measure clock drift between devices.
          Select a reference file and a target file from the same session.
        </p>

        <!-- File selectors -->
        <div class="file-row">
          <div class="file-label">Reference</div>
          <button class="file-picker" @click="pickReference">
            <span class="file-name" :class="{ empty: !referencePath }">{{ refName }}</span>
            <span class="file-browse">Browse</span>
          </button>
        </div>

        <div class="file-row">
          <div class="file-label">Target</div>
          <button class="file-picker" @click="pickTarget">
            <span class="file-name" :class="{ empty: !targetPath }">{{ tgtName }}</span>
            <span class="file-browse">Browse</span>
          </button>
        </div>

        <!-- Measure button -->
        <button
          class="btn btn-primary measure-btn"
          :disabled="!canMeasure"
          @click="runMeasurement"
        >
          <span v-if="measuring" class="spin">&#x21BB;</span>
          <span v-else>Measure Drift</span>
        </button>

        <!-- Results -->
        <Transition name="slide-up">
          <div v-if="result" class="results">
            <div class="result-grid">
              <div class="result-item">
                <span class="result-label">Delay</span>
                <span class="result-value">{{ result.delay_s.toFixed(3) }}s</span>
                <span class="result-sub">{{ result.delay_samples }} samples</span>
              </div>
              <div class="result-item">
                <span class="result-label">Confidence</span>
                <span
                  class="result-value"
                  :class="{
                    'conf-high': result.confidence >= 5,
                    'conf-ok': result.confidence >= 3 && result.confidence < 5,
                    'conf-low': result.confidence < 3,
                  }"
                >
                  {{ result.confidence.toFixed(1) }}
                </span>
              </div>
              <div class="result-item">
                <span class="result-label">Drift</span>
                <span
                  class="result-value"
                  :class="{ 'drift-significant': result.drift_significant }"
                >
                  {{ formatPpm(result.drift_ppm) }}
                </span>
              </div>
              <div class="result-item">
                <span class="result-label">R-squared</span>
                <span class="result-value">{{ result.drift_r_squared.toFixed(4) }}</span>
              </div>
            </div>

            <div
              class="result-status"
              :class="{
                'status-drift': result.drift_significant,
                'status-ok': !result.drift_significant && result.drift_r_squared > 0.3,
                'status-unknown': result.drift_r_squared <= 0.3,
              }"
            >
              <template v-if="result.drift_significant">
                Drift detected — correction recommended
              </template>
              <template v-else-if="result.drift_r_squared > 0.3">
                No significant drift detected
              </template>
              <template v-else>
                Measurement inconclusive (low R-squared)
              </template>
            </div>
          </div>
        </Transition>
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
  width: 460px;
  max-width: 90vw;
  padding: 28px;
  border-radius: 20px;
  background: rgba(21, 28, 46, 0.95);
  border: 1px solid rgba(56, 189, 248, 0.15);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.5);
  position: relative;
}

.dialog-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
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

.dialog-desc {
  font-size: 12px;
  color: var(--text-dim);
  line-height: 1.6;
  margin-bottom: 20px;
}

.file-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.file-label {
  width: 72px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  flex-shrink: 0;
}

.file-picker {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  cursor: pointer;
  transition: all 0.2s ease;
}

.file-picker:hover {
  border-color: var(--border-light);
  background: rgba(56, 189, 248, 0.04);
}

.file-name {
  font-size: 12px;
  color: var(--text);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.file-name.empty {
  color: var(--text-muted);
  font-style: italic;
}

.file-browse {
  font-size: 11px;
  color: var(--cyan);
  font-weight: 600;
  flex-shrink: 0;
  margin-left: 8px;
}

.measure-btn {
  width: 100%;
  margin-top: 16px;
  margin-bottom: 4px;
}

/* Results */
.results {
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid var(--border-subtle);
}

.result-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
  margin-bottom: 16px;
}

.result-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.result-label {
  font-size: 10px;
  font-weight: 600;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.result-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-bright);
  font-family: var(--font-mono);
}

.result-sub {
  font-size: 10px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.conf-high { color: #34d399; }
.conf-ok { color: #fbbf24; }
.conf-low { color: #fb7185; }
.drift-significant { color: #fbbf24; }

.result-status {
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 600;
  text-align: center;
}

.status-drift {
  background: rgba(251, 191, 36, 0.1);
  border: 1px solid rgba(251, 191, 36, 0.25);
  color: #fbbf24;
}

.status-ok {
  background: rgba(52, 211, 153, 0.1);
  border: 1px solid rgba(52, 211, 153, 0.25);
  color: #34d399;
}

.status-unknown {
  background: rgba(139, 149, 184, 0.1);
  border: 1px solid rgba(139, 149, 184, 0.2);
  color: var(--text-dim);
}
</style>
