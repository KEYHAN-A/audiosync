<script setup>
defineProps({
  visible: { type: Boolean, default: false },
  version: { type: String, default: "3.0.0" },
});

const emit = defineEmits(["close"]);

function openUrl(url) {
  window.__TAURI__?.core?.invoke("plugin:shell|open", { path: url }).catch(() => {
    window.open(url, "_blank");
  });
}
</script>

<template>
  <Transition name="scale">
    <div v-if="visible" class="dialog-overlay" @click.self="emit('close')">
      <div class="dialog">
        <div class="about-header">
          <img src="/icon.png" alt="AudioSync Pro" class="about-icon" />
          <h2 class="about-title gradient-text">AudioSync Pro</h2>
          <p class="about-version">v{{ version }}</p>
        </div>

        <p class="about-desc">
          Multi-device audio/video synchronization with FFT cross-correlation,
          automatic clock drift detection, and NLE timeline export.
        </p>

        <div class="about-tech">
          <span class="tech-badge">Rust</span>
          <span class="tech-badge">Tauri v2</span>
          <span class="tech-badge">Vue 3</span>
          <span class="tech-badge">Canvas</span>
        </div>

        <div class="about-links">
          <button class="link-btn" @click="openUrl('https://audiosync.pro')">
            <span class="link-icon">&#x1F310;</span> Website
          </button>
          <button class="link-btn" @click="openUrl('https://github.com/KEYHAN-A/audiosync')">
            <span class="link-icon">&#x2B50;</span> GitHub
          </button>
          <button class="link-btn" @click="openUrl('https://github.com/KEYHAN-A/audiosync/issues')">
            <span class="link-icon">&#x1F41B;</span> Report Issue
          </button>
        </div>

        <div class="about-footer">
          <p class="about-credit">Created by Keyhan</p>
          <p class="about-license">GPL-3.0 License</p>
        </div>

        <button class="close-btn" @click="emit('close')">&times;</button>
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
  width: 380px;
  max-width: 90vw;
  padding: 32px;
  border-radius: 24px;
  background: rgba(21, 28, 46, 0.95);
  border: 1px solid rgba(56, 189, 248, 0.15);
  box-shadow: 0 24px 64px rgba(0, 0, 0, 0.5);
  text-align: center;
  position: relative;
}

.about-header {
  margin-bottom: 20px;
}

.about-icon {
  width: 64px;
  height: 64px;
  border-radius: 16px;
  margin-bottom: 12px;
  box-shadow: 0 8px 24px rgba(56, 189, 248, 0.15);
}

.about-title {
  font-size: 22px;
  font-weight: 800;
  letter-spacing: -0.5px;
  margin-bottom: 4px;
}

.about-version {
  font-size: 13px;
  color: var(--text-muted);
  font-family: var(--font-mono);
}

.about-desc {
  font-size: 12px;
  color: var(--text-dim);
  line-height: 1.6;
  margin-bottom: 20px;
  padding: 0 8px;
}

.about-tech {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.tech-badge {
  padding: 4px 12px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 600;
  background: rgba(56, 189, 248, 0.08);
  color: var(--cyan);
  border: 1px solid rgba(56, 189, 248, 0.15);
}

.about-links {
  display: flex;
  justify-content: center;
  gap: 8px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.link-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border: 1px solid var(--border-subtle);
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.03);
  color: var(--text);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.link-btn:hover {
  background: rgba(56, 189, 248, 0.06);
  border-color: var(--border-light);
  color: var(--text-bright);
}

.link-icon {
  font-size: 14px;
}

.about-footer {
  padding-top: 16px;
  border-top: 1px solid var(--border-subtle);
}

.about-credit {
  font-size: 12px;
  color: var(--text-dim);
  margin-bottom: 2px;
}

.about-license {
  font-size: 10px;
  color: var(--text-muted);
}

.close-btn {
  position: absolute;
  top: 12px;
  right: 12px;
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
</style>
