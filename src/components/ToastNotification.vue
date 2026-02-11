<script setup>
import { useToast } from "../composables/useToast.js";
const { state, hideToast } = useToast();

const icons = {
  success: "\u2713",
  error: "\u2717",
  warning: "\u26A0",
  info: "\u2139",
};
</script>

<template>
  <Transition name="toast">
    <div
      v-if="state.visible"
      class="toast"
      :class="state.type"
      @click="hideToast"
    >
      <span class="toast-icon">{{ icons[state.type] || icons.info }}</span>
      <span class="toast-message">{{ state.message }}</span>
    </div>
  </Transition>
</template>

<style scoped>
.toast {
  position: fixed;
  bottom: 24px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 24px;
  border-radius: 14px;
  background: rgba(21, 28, 46, 0.95);
  backdrop-filter: blur(20px);
  -webkit-backdrop-filter: blur(20px);
  border: 1px solid var(--border-light);
  color: var(--text);
  font-size: 13px;
  z-index: 10000;
  cursor: pointer;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
  max-width: 500px;
}

.toast.success {
  border-color: rgba(52, 211, 153, 0.4);
}
.toast.success .toast-icon {
  color: #34d399;
}

.toast.error {
  border-color: rgba(248, 113, 113, 0.4);
}
.toast.error .toast-icon {
  color: #f87171;
}

.toast.warning {
  border-color: rgba(251, 191, 36, 0.4);
}
.toast.warning .toast-icon {
  color: #fbbf24;
}

.toast.info .toast-icon {
  color: var(--cyan);
}

.toast-icon {
  font-size: 16px;
  flex-shrink: 0;
}

.toast-message {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Transition */
.toast-enter-active {
  transition: all 0.4s cubic-bezier(0.34, 1.56, 0.64, 1);
}
.toast-leave-active {
  transition: all 0.3s ease-in;
}
.toast-enter-from {
  opacity: 0;
  transform: translateX(-50%) translateY(20px) scale(0.95);
}
.toast-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(10px) scale(0.98);
}
</style>
