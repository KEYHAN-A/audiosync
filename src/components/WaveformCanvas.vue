<script setup>
import { ref, onMounted, onUnmounted, watch, computed } from "vue";

const props = defineProps({
  tracks: { type: Array, default: () => [] },
  analysisResult: { type: Object, default: null },
  timelineDuration: { type: Number, default: 0 },
});

const canvas = ref(null);
const container = ref(null);
let animationId = null;
let resizeObserver = null;

const trackColors = [
  "#38bdf8", "#a78bfa", "#2dd4bf", "#fb7185",
  "#fbbf24", "#818cf8", "#34d399", "#e879f9",
];

// View state
const zoom = ref(1);
const scrollX = ref(0);

const RULER_H = 30;
const LANE_H = 80;
const LANE_GAP = 4;
const LANE_PADDING = 8;
const LABEL_W = 90;

const hasData = computed(
  () => props.tracks.length > 0 && props.tracks.some((t) => t.clips?.length > 0)
);

const isAnalyzed = computed(
  () => props.analysisResult !== null && props.analysisResult.total_timeline_s > 0
);

// ---------------------------------------------------------------------------
//  Drawing
// ---------------------------------------------------------------------------

function draw() {
  const cvs = canvas.value;
  if (!cvs) return;

  const ctx = cvs.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  const rect = cvs.getBoundingClientRect();
  const w = rect.width;
  const h = rect.height;

  cvs.width = w * dpr;
  cvs.height = h * dpr;
  ctx.scale(dpr, dpr);

  // Background
  ctx.fillStyle = "#0a0e1a";
  ctx.beginPath();
  roundRect(ctx, 0, 0, w, h, 14);
  ctx.fill();

  // Border
  ctx.strokeStyle = "rgba(56, 189, 248, 0.12)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  roundRect(ctx, 0.5, 0.5, w - 1, h - 1, 14);
  ctx.stroke();

  if (!hasData.value) {
    drawEmptyState(ctx, w, h);
    return;
  }

  if (isAnalyzed.value) {
    drawTimeline(ctx, w, h);
  } else {
    drawPreAnalysis(ctx, w, h);
  }
}

function drawEmptyState(ctx, w, h) {
  ctx.fillStyle = "#8b95b8";
  ctx.font = "bold 14px Inter, system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.fillText("Timeline", w / 2, h / 2 - 12);

  ctx.fillStyle = "rgba(139, 149, 184, 0.6)";
  ctx.font = "11px Inter, system-ui, sans-serif";
  ctx.fillText(
    "Import files and run analysis to see the waveform timeline",
    w / 2,
    h / 2 + 12
  );

  drawDecorativeWave(ctx, w, h);
}

function drawDecorativeWave(ctx, w, h) {
  const time = Date.now() / 1000;
  const centerY = h / 2 + 40;
  const amplitude = 8;
  const points = 200;

  ctx.beginPath();
  ctx.strokeStyle = "rgba(56, 189, 248, 0.15)";
  ctx.lineWidth = 1.5;

  for (let i = 0; i <= points; i++) {
    const x = (i / points) * w;
    const y =
      centerY +
      Math.sin(x * 0.02 + time * 2) * amplitude +
      Math.sin(x * 0.035 + time * 1.5) * amplitude * 0.5;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  ctx.beginPath();
  ctx.strokeStyle = "rgba(167, 139, 250, 0.10)";
  for (let i = 0; i <= points; i++) {
    const x = (i / points) * w;
    const y =
      centerY +
      Math.sin(x * 0.025 + time * 1.3 + 1) * amplitude * 0.8 +
      Math.sin(x * 0.04 + time * 1.8) * amplitude * 0.3;
    if (i === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();

  animationId = requestAnimationFrame(() => draw());
}

// Pre-analysis: show waveform previews per track (no offset info)
function drawPreAnalysis(ctx, w, h) {
  drawRuler(ctx, w, 0);
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, RULER_H, w, h - RULER_H);
  ctx.clip();

  const trackCount = props.tracks.length;
  for (let ti = 0; ti < trackCount; ti++) {
    const track = props.tracks[ti];
    const color = trackColors[ti % trackColors.length];
    const y = RULER_H + ti * (LANE_H + LANE_GAP) + LANE_GAP;

    drawLane(ctx, 0, y, w, LANE_H, color, track.name, track.is_reference);

    // Draw waveform peaks stacked for each clip
    const clipAreaX = LABEL_W;
    const clipAreaW = w - LABEL_W - 8;
    let xPos = clipAreaX;

    for (const clip of track.clips || []) {
      const peaks = clip.waveform_peaks;
      if (!peaks || peaks.length === 0) continue;

      const totalDur = track.total_duration_s || 1;
      const clipW = (clip.duration_s / totalDur) * clipAreaW;

      drawWaveform(ctx, peaks, xPos, y + 12, clipW, LANE_H - 24, color);
      xPos += clipW + 2;
    }
  }

  ctx.restore();
}

// Post-analysis: draw clips on a timeline with offsets
function drawTimeline(ctx, w, h) {
  const duration = props.timelineDuration || 1;
  const timelineW = (w - LABEL_W - 8) * zoom.value;
  const pxPerSec = timelineW / duration;

  drawRuler(ctx, w, duration);

  ctx.save();
  ctx.beginPath();
  ctx.rect(0, RULER_H, w, h - RULER_H);
  ctx.clip();

  const trackCount = props.tracks.length;
  for (let ti = 0; ti < trackCount; ti++) {
    const track = props.tracks[ti];
    const color = trackColors[ti % trackColors.length];
    const y = RULER_H + ti * (LANE_H + LANE_GAP) + LANE_GAP;

    drawLane(ctx, 0, y, w, LANE_H, color, track.name, track.is_reference);

    for (const clip of track.clips || []) {
      const peaks = clip.waveform_peaks;
      const clipX = LABEL_W + clip.timeline_offset_s * pxPerSec - scrollX.value;
      const clipW = clip.duration_s * pxPerSec;

      if (clipX + clipW < LABEL_W || clipX > w) continue;

      // Clip background
      ctx.fillStyle = hexToRgba(color, 0.08);
      roundRectFill(ctx, Math.max(clipX, LABEL_W), y + 4, clipW, LANE_H - 8, 6);

      // Clip border
      ctx.strokeStyle = hexToRgba(color, 0.3);
      ctx.lineWidth = 1;
      ctx.beginPath();
      roundRect(ctx, Math.max(clipX, LABEL_W) + 0.5, y + 4.5, clipW - 1, LANE_H - 9, 6);
      ctx.stroke();

      // Waveform
      if (peaks && peaks.length > 0) {
        const drawX = Math.max(clipX, LABEL_W);
        const drawW = Math.min(clipW, w - drawX);
        drawWaveform(ctx, peaks, drawX + 4, y + 14, drawW - 8, LANE_H - 28, color);
      }

      // Clip name label
      ctx.fillStyle = hexToRgba(color, 0.8);
      ctx.font = "600 9px Inter, system-ui, sans-serif";
      ctx.textAlign = "left";
      const labelX = Math.max(clipX + 6, LABEL_W + 6);
      ctx.fillText(clip.name, labelX, y + LANE_H - 8);
    }
  }

  // Playhead position indicator (center line)
  if (isAnalyzed.value) {
    const centerX = LABEL_W;
    ctx.strokeStyle = "rgba(56, 189, 248, 0.4)";
    ctx.lineWidth = 1;
    ctx.setLineDash([4, 4]);
    ctx.beginPath();
    ctx.moveTo(centerX, RULER_H);
    ctx.lineTo(centerX, h);
    ctx.stroke();
    ctx.setLineDash([]);
  }

  ctx.restore();
}

// ---------------------------------------------------------------------------
//  Drawing primitives
// ---------------------------------------------------------------------------

function drawRuler(ctx, w, duration) {
  ctx.fillStyle = "#111827";
  ctx.fillRect(0, 0, w, RULER_H);

  ctx.strokeStyle = "rgba(56, 189, 248, 0.12)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, RULER_H - 0.5);
  ctx.lineTo(w, RULER_H - 0.5);
  ctx.stroke();

  if (duration <= 0) return;

  const timelineW = (w - LABEL_W - 8) * zoom.value;
  const pxPerSec = timelineW / duration;

  // Determine tick interval
  let interval = 1;
  if (pxPerSec < 3) interval = 60;
  else if (pxPerSec < 10) interval = 30;
  else if (pxPerSec < 30) interval = 10;
  else if (pxPerSec < 80) interval = 5;

  ctx.fillStyle = "rgba(139, 149, 184, 0.5)";
  ctx.font = "10px 'JetBrains Mono', 'SF Mono', monospace";
  ctx.textAlign = "center";

  for (let t = 0; t <= duration; t += interval) {
    const x = LABEL_W + t * pxPerSec - scrollX.value;
    if (x < LABEL_W || x > w) continue;

    // Tick mark
    ctx.strokeStyle = "rgba(56, 189, 248, 0.15)";
    ctx.beginPath();
    ctx.moveTo(x, RULER_H - 8);
    ctx.lineTo(x, RULER_H);
    ctx.stroke();

    // Time label
    const m = Math.floor(t / 60);
    const s = Math.floor(t % 60);
    ctx.fillText(`${m}:${s.toString().padStart(2, "0")}`, x, RULER_H - 12);
  }
}

function drawLane(ctx, x, y, w, h, color, name, isRef) {
  // Lane background
  ctx.fillStyle = "rgba(17, 24, 39, 0.4)";
  ctx.fillRect(0, y, LABEL_W - 4, h);

  // Track label
  ctx.fillStyle = hexToRgba(color, 0.9);
  ctx.font = "600 11px Inter, system-ui, sans-serif";
  ctx.textAlign = "left";
  ctx.fillText(name, 10, y + 18);

  if (isRef) {
    ctx.fillStyle = "rgba(56, 189, 248, 0.5)";
    ctx.font = "bold 8px Inter, system-ui, sans-serif";
    ctx.fillText("REF", 10, y + 32);
  }

  // Lane separator
  ctx.strokeStyle = "rgba(56, 189, 248, 0.06)";
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, y + h + LANE_GAP / 2);
  ctx.lineTo(w, y + h + LANE_GAP / 2);
  ctx.stroke();
}

function drawWaveform(ctx, peaks, x, y, w, h, color) {
  if (!peaks || peaks.length === 0 || w <= 0 || h <= 0) return;

  const n = peaks.length;
  const centerY = y + h / 2;
  const halfH = h / 2;

  // Filled waveform
  ctx.beginPath();
  for (let i = 0; i < n; i++) {
    const px = x + (i / n) * w;
    const amp = Math.min(peaks[i], 1.0) * halfH;
    if (i === 0) ctx.moveTo(px, centerY - amp);
    else ctx.lineTo(px, centerY - amp);
  }
  for (let i = n - 1; i >= 0; i--) {
    const px = x + (i / n) * w;
    const amp = Math.min(peaks[i], 1.0) * halfH;
    ctx.lineTo(px, centerY + amp);
  }
  ctx.closePath();

  const grad = ctx.createLinearGradient(x, y, x, y + h);
  grad.addColorStop(0, hexToRgba(color, 0.5));
  grad.addColorStop(0.5, hexToRgba(color, 0.2));
  grad.addColorStop(1, hexToRgba(color, 0.5));
  ctx.fillStyle = grad;
  ctx.fill();

  // Waveform outline (top)
  ctx.beginPath();
  ctx.strokeStyle = hexToRgba(color, 0.7);
  ctx.lineWidth = 1;
  for (let i = 0; i < n; i++) {
    const px = x + (i / n) * w;
    const amp = Math.min(peaks[i], 1.0) * halfH;
    if (i === 0) ctx.moveTo(px, centerY - amp);
    else ctx.lineTo(px, centerY - amp);
  }
  ctx.stroke();

  // Center line
  ctx.strokeStyle = hexToRgba(color, 0.1);
  ctx.beginPath();
  ctx.moveTo(x, centerY);
  ctx.lineTo(x + w, centerY);
  ctx.stroke();
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function roundRectFill(ctx, x, y, w, h, r) {
  ctx.beginPath();
  roundRect(ctx, x, y, w, h, r);
  ctx.fill();
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// ---------------------------------------------------------------------------
//  Interaction
// ---------------------------------------------------------------------------

function handleWheel(e) {
  if (e.ctrlKey || e.metaKey) {
    e.preventDefault();
    const delta = e.deltaY > 0 ? 0.9 : 1.1;
    zoom.value = Math.max(0.1, Math.min(20, zoom.value * delta));
    draw();
  } else {
    scrollX.value = Math.max(0, scrollX.value + e.deltaX);
    draw();
  }
}

// ---------------------------------------------------------------------------
//  Lifecycle
// ---------------------------------------------------------------------------

function handleResize() {
  draw();
}

onMounted(() => {
  draw();
  resizeObserver = new ResizeObserver(handleResize);
  if (container.value) {
    resizeObserver.observe(container.value);
  }
});

onUnmounted(() => {
  if (animationId) cancelAnimationFrame(animationId);
  if (resizeObserver) resizeObserver.disconnect();
});

watch(
  () => [props.tracks, props.analysisResult, props.timelineDuration],
  () => {
    // Cancel animation when we have data
    if (animationId && hasData.value) {
      cancelAnimationFrame(animationId);
      animationId = null;
    }
    draw();
  },
  { deep: true }
);
</script>

<template>
  <div ref="container" class="waveform-container">
    <canvas
      ref="canvas"
      class="waveform-canvas"
      @wheel="handleWheel"
    ></canvas>
    <div v-if="isAnalyzed" class="zoom-indicator">
      {{ Math.round(zoom * 100) }}%
    </div>
  </div>
</template>

<style scoped>
.waveform-container {
  width: 100%;
  height: 100%;
  position: relative;
}

.waveform-canvas {
  width: 100%;
  height: 100%;
  display: block;
  border-radius: 14px;
}

.zoom-indicator {
  position: absolute;
  bottom: 12px;
  right: 12px;
  font-size: 10px;
  font-family: "JetBrains Mono", "SF Mono", monospace;
  color: var(--text-muted);
  background: rgba(17, 24, 39, 0.7);
  padding: 2px 8px;
  border-radius: 6px;
  border: 1px solid var(--border-subtle);
}
</style>
