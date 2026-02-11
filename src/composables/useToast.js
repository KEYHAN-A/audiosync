/**
 * useToast — Simple toast notification system.
 *
 * Usage:
 *   const { showToast } = useToast();
 *   showToast("Files imported!", "success");
 *   showToast("Something went wrong", "error");
 */

import { reactive } from "vue";

const state = reactive({
  visible: false,
  message: "",
  type: "info", // "info" | "success" | "error" | "warning"
  timeoutId: null,
});

function showToast(message, type = "info", duration = 3000) {
  if (state.timeoutId) clearTimeout(state.timeoutId);

  state.message = message;
  state.type = type;
  state.visible = true;

  state.timeoutId = setTimeout(() => {
    state.visible = false;
    state.timeoutId = null;
  }, duration);
}

function hideToast() {
  if (state.timeoutId) clearTimeout(state.timeoutId);
  state.visible = false;
  state.timeoutId = null;
}

export function useToast() {
  return { state, showToast, hideToast };
}
