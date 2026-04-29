<script setup>
import { ref, onMounted } from "vue";

const emit = defineEmits(["dismiss", "importFiles"]);

const visible = ref(false);
const isDragOver = ref(false);

onMounted(async () => {
  visible.value = true;
});

function handleGetStarted() {
  dismiss();
}

function dismiss() {
  visible.value = false;
  emit("dismiss");
}

function handleImportClick() {
  dismiss();
  emit("importFiles");
}
</script>

<template>
  <Transition name="onboarding">
    <div v-if="visible" class="onboarding-backdrop" @dragover.prevent="isDragOver = true"
      @dragleave="isDragOver = false" @drop.prevent="isDragOver = false">
      <div class="onboarding-content" :class="{ 'drag-active': isDragOver }">
        <!-- Close button -->
        <button class="onboarding-skip" @click="dismiss" title="Skip onboarding">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
          </svg>
          Skip
        </button>

        <!-- Icon -->
        <div class="onboarding-icon">
          <div class="icon-ring"></div>
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round"
              d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z" />
          </svg>
        </div>

        <!-- Title -->
        <h1 class="onboarding-title">
          <span class="gradient-text">AudioSync Pro</span>
        </h1>
        <p class="onboarding-subtitle">
          Sync recordings from all your cameras, mics, and recorders with sample-accurate precision.
        </p>

        <!-- 3-step workflow -->
        <div class="onboarding-steps">
          <div class="step-card">
            <div class="step-number">1</div>
            <div class="step-content">
              <h3>Import</h3>
              <p>Drop your audio or video files. They're grouped by device automatically.</p>
            </div>
          </div>

          <div class="step-connector">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </div>

          <div class="step-card">
            <div class="step-number">2</div>
            <div class="step-content">
              <h3>Analyze</h3>
              <p>FFT cross-correlation finds exact sync offsets. Clock drift is auto-detected.</p>
            </div>
          </div>

          <div class="step-connector">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M13 7l5 5m0 0l-5 5m5-5H6" />
            </svg>
          </div>

          <div class="step-card">
            <div class="step-number">3</div>
            <div class="step-content">
              <h3>Export</h3>
              <p>Get synced audio files + NLE timelines for DaVinci Resolve, Final Cut, or Premiere.</p>
            </div>
          </div>
        </div>

        <!-- Drop zone / CTA -->
        <div class="onboarding-cta" @click="handleImportClick">
          <div class="cta-content">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round"
                d="M12 16v-8m0 0l-3 3m3-3l3 3M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5" />
            </svg>
            <div>
              <p class="cta-title">Drop your files here to get started</p>
              <p class="cta-subtitle">or click to browse &middot; WAV, MP4, MOV, FLAC & more</p>
            </div>
          </div>
        </div>

        <p class="onboarding-hint">
          Supports WAV, AIFF, FLAC, MP3, MP4, MOV, MKV and more
        </p>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.onboarding-backdrop {
  position: fixed;
  inset: 0;
  z-index: 200;
  background: rgba(5, 8, 22, 0.92);
  backdrop-filter: blur(24px);
  -webkit-backdrop-filter: blur(24px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.onboarding-content {
  position: relative;
  max-width: 640px;
  width: 90%;
  padding: 48px 40px;
  text-align: center;
  background: var(--glass);
  border: 1px solid var(--glass-border);
  border-radius: 24px;
  transition: all 0.3s ease;
}

.onboarding-content.drag-active {
  border-color: var(--cyan);
  box-shadow: 0 0 40px var(--glass-glow);
}

/* Skip button */
.onboarding-skip {
  position: absolute;
  top: 16px;
  right: 16px;
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 10px;
  background: transparent;
  border: 1px solid var(--border-subtle);
  border-radius: 8px;
  color: var(--text-muted);
  font-size: 11px;
  cursor: pointer;
  transition: all 0.2s ease;
}
.onboarding-skip:hover {
  color: var(--text-dim);
  border-color: var(--border-light);
}

/* Icon */
.onboarding-icon {
  position: relative;
  width: 80px;
  height: 80px;
  margin: 0 auto 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--cyan);
}
.icon-ring {
  position: absolute;
  inset: 0;
  border-radius: 20px;
  border: 2px solid var(--cyan);
  opacity: 0.2;
  animation: iconPulse 3s ease-in-out infinite;
}
@keyframes iconPulse {
  0%, 100% { transform: scale(1); opacity: 0.2; }
  50% { transform: scale(1.1); opacity: 0.35; }
}

/* Title */
.onboarding-title {
  font-size: 28px;
  font-weight: 800;
  letter-spacing: -0.5px;
  margin-bottom: 8px;
}
.onboarding-subtitle {
  font-size: 14px;
  color: var(--text-dim);
  max-width: 420px;
  margin: 0 auto 36px;
  line-height: 1.6;
}

/* Steps */
.onboarding-steps {
  display: flex;
  align-items: flex-start;
  justify-content: center;
  gap: 12px;
  margin-bottom: 36px;
}
.step-card {
  flex: 1;
  max-width: 160px;
  text-align: center;
}
.step-number {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-weight: 700;
  font-size: 16px;
  margin: 0 auto 12px;
  color: var(--navy-deep);
}
.step-card:nth-child(1) .step-number { background: var(--cyan); }
.step-card:nth-child(3) .step-number { background: var(--purple); }
.step-card:nth-child(5) .step-number { background: var(--cyan); }
.step-content h3 {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-bright);
  margin-bottom: 4px;
}
.step-content p {
  font-size: 11px;
  color: var(--text-dim);
  line-height: 1.5;
}
.step-connector {
  flex-shrink: 0;
  color: var(--text-muted);
  margin-top: 10px;
}

/* CTA */
.onboarding-cta {
  cursor: pointer;
  padding: 20px 28px;
  border-radius: 16px;
  border: 2px dashed var(--border-light);
  background: rgba(56, 189, 248, 0.04);
  transition: all 0.3s ease;
  margin-bottom: 16px;
}
.onboarding-cta:hover {
  border-color: var(--cyan);
  background: rgba(56, 189, 248, 0.08);
}
.cta-content {
  display: flex;
  align-items: center;
  gap: 16px;
  color: var(--cyan);
  text-align: left;
}
.cta-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-bright);
  margin-bottom: 2px;
}
.cta-subtitle {
  font-size: 12px;
  color: var(--text-dim);
}

/* Hint */
.onboarding-hint {
  font-size: 11px;
  color: var(--text-muted);
}

/* Transition */
.onboarding-enter-active {
  transition: opacity 0.4s ease;
}
.onboarding-leave-active {
  transition: opacity 0.3s ease;
}
.onboarding-enter-from,
.onboarding-leave-to {
  opacity: 0;
}

/* Responsive */
@media (max-width: 640px) {
  .onboarding-steps {
    flex-direction: column;
    align-items: center;
  }
  .step-connector {
    transform: rotate(90deg);
    margin: 4px 0;
  }
  .step-card {
    max-width: 260px;
  }
  .onboarding-content {
    padding: 36px 24px;
  }
}
</style>
