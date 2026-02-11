<script setup>
import { ref } from "vue";
import { useCloud } from "../composables/useCloud.js";
import { useAuth } from "../composables/useAuth.js";
import { writeText } from "@tauri-apps/plugin-clipboard-manager";

const props = defineProps({
  visible: { type: Boolean, default: false },
  tracks: { type: Array, default: () => [] },
  analysisResult: { type: Object, default: null },
});

const emit = defineEmits(["close"]);

const { shareTimeline, state: cloudState } = useCloud();
const { isLoggedIn } = useAuth();

const shareUrl = ref(null);
const copied = ref(false);
const projectName = ref("AudioSync Pro Timeline");

async function handleShare() {
  if (!props.tracks.length || !props.analysisResult) return;

  const timelineData = {
    tracks: props.tracks,
    analysisResult: props.analysisResult,
  };

  const url = await shareTimeline(projectName.value, timelineData);
  if (url) {
    shareUrl.value = url;
  }
}

async function copyLink() {
  if (!shareUrl.value) return;
  try {
    await writeText(shareUrl.value);
    copied.value = true;
    setTimeout(() => (copied.value = false), 2000);
  } catch {
    // Fallback: try navigator clipboard
    try {
      await navigator.clipboard.writeText(shareUrl.value);
      copied.value = true;
      setTimeout(() => (copied.value = false), 2000);
    } catch {
      // Can't copy
    }
  }
}

function handleClose() {
  shareUrl.value = null;
  copied.value = false;
  emit("close");
}
</script>

<template>
  <Transition name="fade">
    <div v-if="visible" class="dialog-overlay" @click.self="handleClose">
      <div class="dialog glass-card">
        <div class="dialog-header">
          <h3 class="dialog-title">Share Timeline</h3>
          <button class="close-btn" @click="handleClose">&times;</button>
        </div>

        <!-- Not logged in -->
        <div v-if="!isLoggedIn" class="not-logged-in">
          <p>Sign in to share your timeline with others.</p>
        </div>

        <!-- Share URL generated -->
        <div v-else-if="shareUrl" class="share-result">
          <div class="success-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <p class="result-text">Your timeline is now shared!</p>
          <div class="url-box" @click="copyLink">
            <span class="url-text">{{ shareUrl }}</span>
            <span class="copy-label">{{ copied ? "Copied!" : "Click to copy" }}</span>
          </div>
          <p class="hint-text">Anyone with this link can view the timeline and download the FCPXML.</p>
        </div>

        <!-- Share form -->
        <div v-else class="share-form">
          <div class="share-icon">
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M7.217 10.907a2.25 2.25 0 100 2.186m0-2.186c.18.324.283.696.283 1.093s-.103.77-.283 1.093m0-2.186l9.566-5.314m-9.566 7.5l9.566 5.314m0 0a2.25 2.25 0 103.935 2.186 2.25 2.25 0 00-3.935-2.186zm0-12.814a2.25 2.25 0 103.933-2.185 2.25 2.25 0 00-3.933 2.185z" />
            </svg>
          </div>

          <p class="share-desc">
            Create a shareable link to your timeline. Recipients can view the waveform layout and download the FCPXML.
          </p>

          <div class="form-group">
            <label class="form-label">Project Name</label>
            <input
              v-model="projectName"
              class="form-input"
              type="text"
              placeholder="My Timeline"
            />
          </div>

          <div class="share-stats">
            <span>{{ tracks.length }} tracks</span>
            <span class="dot"></span>
            <span>{{ tracks.reduce((n, t) => n + (t.clips?.length || 0), 0) }} clips</span>
            <span class="dot"></span>
            <span>{{ (analysisResult?.total_timeline_s / 60).toFixed(1) }} min</span>
          </div>

          <button
            class="btn btn-primary btn-block"
            @click="handleShare"
            :disabled="cloudState.isLoading || !projectName.trim()"
          >
            {{ cloudState.isLoading ? "Sharing..." : "Create Share Link" }}
          </button>

          <p v-if="cloudState.error" class="error-text">{{ cloudState.error }}</p>
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
  width: 440px;
  max-width: 90vw;
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

.not-logged-in {
  text-align: center;
  padding: 20px 0;
  color: var(--text-muted);
  font-size: 13px;
}

/* Share form */
.share-form {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.share-icon {
  color: var(--cyan, #38bdf8);
  margin-bottom: 12px;
  opacity: 0.7;
}

.share-desc {
  font-size: 12px;
  color: var(--text-muted);
  line-height: 1.6;
  max-width: 340px;
  margin-bottom: 20px;
}

.form-group {
  width: 100%;
  margin-bottom: 16px;
  text-align: left;
}

.form-label {
  display: block;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-dim);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 6px;
}

.form-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border-light, rgba(56, 189, 248, 0.2));
  border-radius: 10px;
  background: var(--bg-input, rgba(10, 14, 26, 0.6));
  color: var(--text, #cbd5e1);
  font-size: 13px;
  outline: none;
  transition: border-color 0.2s ease;
  box-sizing: border-box;
}

.form-input:focus {
  border-color: var(--cyan, #38bdf8);
}

.share-stats {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11px;
  color: var(--text-muted);
  margin-bottom: 20px;
}

.dot {
  width: 3px;
  height: 3px;
  border-radius: 50%;
  background: var(--text-muted);
}

.btn-block {
  width: 100%;
}

.error-text {
  margin-top: 10px;
  font-size: 12px;
  color: #ef4444;
}

/* Share result */
.share-result {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.success-icon {
  color: #34d399;
  margin-bottom: 12px;
}

.result-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-bright);
  margin-bottom: 16px;
}

.url-box {
  width: 100%;
  padding: 12px 16px;
  background: rgba(56, 189, 248, 0.06);
  border: 1px solid rgba(56, 189, 248, 0.2);
  border-radius: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  margin-bottom: 16px;
}

.url-box:hover {
  border-color: rgba(56, 189, 248, 0.4);
  background: rgba(56, 189, 248, 0.1);
}

.url-text {
  display: block;
  font-size: 12px;
  font-family: "JetBrains Mono", "SF Mono", monospace;
  color: var(--cyan, #38bdf8);
  word-break: break-all;
  margin-bottom: 4px;
}

.copy-label {
  font-size: 10px;
  color: var(--text-muted);
}

.hint-text {
  font-size: 11px;
  color: var(--text-muted);
  line-height: 1.5;
  max-width: 300px;
}
</style>
