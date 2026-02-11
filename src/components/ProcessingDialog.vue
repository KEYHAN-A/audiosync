<script setup>
import { computed } from "vue";

const props = defineProps({
  visible: { type: Boolean, default: false },
  title: { type: String, default: "Processing" },
  step: { type: Number, default: 0 },
  total: { type: Number, default: 0 },
  message: { type: String, default: "" },
});

const emit = defineEmits(["cancel"]);

const progress = computed(() => {
  if (props.total <= 0) return 0;
  return Math.min(100, Math.round((props.step / props.total) * 100));
});
</script>

<template>
  <Transition name="fade">
    <div v-if="visible" class="dialog-overlay" @click.self="emit('cancel')">
      <div class="dialog glass-card">
        <div class="dialog-header">
          <h3 class="dialog-title">{{ title }}</h3>
          <span class="dialog-step">{{ step }} / {{ total }}</span>
        </div>

        <div class="progress-track">
          <div class="progress-fill" :style="{ width: progress + '%' }">
            <div class="progress-shimmer"></div>
          </div>
        </div>

        <p class="dialog-message">{{ message }}</p>

        <div class="dialog-actions">
          <button class="btn btn-ghost btn-sm" @click="emit('cancel')">
            Cancel (Esc)
          </button>
          <span class="dialog-percent">{{ progress }}%</span>
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
  width: 420px;
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
  margin-bottom: 20px;
}

.dialog-title {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-bright);
}

.dialog-step {
  font-size: 12px;
  font-family: "JetBrains Mono", "SF Mono", monospace;
  color: var(--text-muted);
}

.progress-track {
  height: 6px;
  background: rgba(255, 255, 255, 0.06);
  border-radius: 3px;
  overflow: hidden;
  margin-bottom: 16px;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--cyan), var(--purple));
  border-radius: 3px;
  transition: width 0.3s ease;
  position: relative;
  overflow: hidden;
}

.progress-shimmer {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.15) 50%,
    transparent 100%
  );
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% { transform: translateX(-100%); }
  100% { transform: translateX(100%); }
}

.dialog-message {
  font-size: 12px;
  color: var(--text-dim);
  min-height: 18px;
  margin-bottom: 20px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.dialog-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.dialog-percent {
  font-size: 12px;
  font-family: "JetBrains Mono", "SF Mono", monospace;
  color: var(--cyan);
  font-weight: 600;
}
</style>
