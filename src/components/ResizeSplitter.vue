<script setup>
import { ref } from "vue";

const props = defineProps({
  initialWidth: { type: Number, default: 340 },
  minWidth: { type: Number, default: 240 },
  maxWidth: { type: Number, default: 600 },
});

const emit = defineEmits(["resize"]);

const panelWidth = ref(props.initialWidth);
const dragging = ref(false);

function onMouseDown(e) {
  e.preventDefault();
  dragging.value = true;
  const startX = e.clientX;
  const startW = panelWidth.value;

  function onMouseMove(e) {
    const delta = e.clientX - startX;
    panelWidth.value = Math.max(
      props.minWidth,
      Math.min(props.maxWidth, startW + delta)
    );
    emit("resize", panelWidth.value);
  }

  function onMouseUp() {
    dragging.value = false;
    document.removeEventListener("mousemove", onMouseMove);
    document.removeEventListener("mouseup", onMouseUp);
  }

  document.addEventListener("mousemove", onMouseMove);
  document.addEventListener("mouseup", onMouseUp);
}
</script>

<template>
  <div class="split-layout" :class="{ dragging }">
    <div class="split-left" :style="{ width: panelWidth + 'px' }">
      <slot name="left"></slot>
    </div>
    <div class="split-handle" @mousedown="onMouseDown">
      <div class="handle-grip"></div>
    </div>
    <div class="split-right">
      <slot name="right"></slot>
    </div>
  </div>
</template>

<style scoped>
.split-layout {
  display: flex;
  flex: 1;
  overflow: hidden;
}

.split-layout.dragging {
  cursor: col-resize;
  user-select: none;
}

.split-left {
  flex-shrink: 0;
  overflow-y: auto;
  overflow-x: hidden;
  background-color: var(--navy-deep);
  padding: 16px;
}

.split-handle {
  width: 5px;
  cursor: col-resize;
  background: var(--border);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background 0.15s ease;
  flex-shrink: 0;
}

.split-handle:hover,
.dragging .split-handle {
  background: var(--cyan);
}

.handle-grip {
  width: 3px;
  height: 32px;
  border-radius: 2px;
  background: rgba(56, 189, 248, 0.3);
  transition: background 0.15s ease;
}

.split-handle:hover .handle-grip,
.dragging .handle-grip {
  background: rgba(56, 189, 248, 0.7);
}

.split-right {
  flex: 1;
  overflow: hidden;
  background-color: var(--navy-deep);
  padding: 16px;
}
</style>
