/**
 * usePlayback — Web Audio API playback engine for synced audio preview.
 *
 * Streams audio chunks from the Rust backend and plays them via Web Audio API
 * with per-track mute/solo/volume controls. All tracks play simultaneously
 * at their correct timeline offsets.
 */

import { ref, computed } from "vue";
import { invoke } from "@tauri-apps/api/core";

const CHUNK_DURATION_S = 5;
const BUFFER_AHEAD_S = 15;

const isPlaying = ref(false);
const isPreparing = ref(false);
const currentTime = ref(0);
const duration = ref(0);
const sampleRate = ref(48000);
const trackCount = ref(0);
const trackMutes = ref([]);
const trackSolos = ref([]);
const trackVolumes = ref([]);

let audioCtx = null;
let sources = [];
let gainNodes = [];
let masterGain = null;
let startTime = 0;
let startOffset = 0;
let animFrameId = null;
let ready = false;

function ensureAudioCtx() {
  if (!audioCtx) {
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  }
  if (audioCtx.state === "suspended") {
    audioCtx.resume();
  }
  return audioCtx;
}

async function prepare() {
  if (isPreparing.value) return;
  isPreparing.value = true;
  ready = false;

  try {
    const info = await invoke("prepare_playback");
    duration.value = info.duration_s;
    sampleRate.value = info.sample_rate;
    trackCount.value = info.track_count;

    trackMutes.value = new Array(info.track_count).fill(false);
    trackSolos.value = new Array(info.track_count).fill(false);
    trackVolumes.value = new Array(info.track_count).fill(1.0);

    ready = true;
    return info;
  } finally {
    isPreparing.value = false;
  }
}

async function play(fromTime = null) {
  if (!ready) await prepare();

  const ctx = ensureAudioCtx();
  stop();

  const offset = fromTime !== null ? fromTime : currentTime.value;
  startOffset = offset;
  startTime = ctx.currentTime;

  masterGain = ctx.createGain();
  masterGain.connect(ctx.destination);
  masterGain.gain.value = 1.0;

  gainNodes = [];
  sources = [];

  const hasSolo = trackSolos.value.some((s) => s);

  for (let t = 0; t < trackCount.value; t++) {
    const muted = hasSolo ? !trackSolos.value[t] : trackMutes.value[t];
    const vol = muted ? 0.0 : trackVolumes.value[t];

    const gain = ctx.createGain();
    gain.gain.value = vol;
    gain.connect(masterGain);
    gainNodes.push(gain);

    const startSample = Math.floor(offset * sampleRate.value);
    const chunkSize = Math.floor(CHUNK_DURATION_S * sampleRate.value);
    const chunksToLoad = Math.ceil(BUFFER_AHEAD_S / CHUNK_DURATION_S);

    const audioBuffers = [];

    for (let c = 0; c < chunksToLoad; c++) {
      const chunkStart = startSample + c * chunkSize;
      if (chunkStart >= Math.floor(duration.value * sampleRate.value)) break;

      try {
        const samples = await invoke("get_audio_chunk", {
          trackIndex: t,
          startSample: chunkStart,
          numSamples: chunkSize,
        });

        if (samples && samples.length > 0) {
          const buf = ctx.createBuffer(1, samples.length, sampleRate.value);
          buf.getChannelData(0).set(samples);
          audioBuffers.push({ buffer: buf, offset: c * CHUNK_DURATION_S });
        }
      } catch (e) {
        console.warn(`Failed to load chunk for track ${t}:`, e);
      }
    }

    if (audioBuffers.length > 0) {
      const source = ctx.createBufferSource();
      const totalSamples = audioBuffers.reduce(
        (sum, b) => sum + b.buffer.length,
        0
      );
      const combined = ctx.createBuffer(1, totalSamples, sampleRate.value);
      const channelData = combined.getChannelData(0);
      let pos = 0;
      for (const { buffer } of audioBuffers) {
        channelData.set(buffer.getChannelData(0), pos);
        pos += buffer.length;
      }

      source.buffer = combined;
      source.connect(gain);
      source.start(0);
      sources.push(source);
    } else {
      sources.push(null);
    }
  }

  isPlaying.value = true;
  startAnimFrame();
}

function stop() {
  if (animFrameId) {
    cancelAnimationFrame(animFrameId);
    animFrameId = null;
  }

  for (const source of sources) {
    try {
      if (source) source.stop();
    } catch (_) {}
  }
  sources = [];
  gainNodes = [];

  if (masterGain) {
    try {
      masterGain.disconnect();
    } catch (_) {}
    masterGain = null;
  }

  isPlaying.value = false;
}

function pause() {
  if (!isPlaying.value) return;
  updateCurrentTime();
  stop();
}

function seek(timeS) {
  const wasPlaying = isPlaying.value;
  if (wasPlaying) {
    updateCurrentTime();
    stop();
  }
  currentTime.value = Math.max(0, Math.min(timeS, duration.value));
  if (wasPlaying) {
    play(currentTime.value);
  }
}

function updateCurrentTime() {
  if (audioCtx && isPlaying.value) {
    currentTime.value = startOffset + (audioCtx.currentTime - startTime);
    if (currentTime.value >= duration.value) {
      currentTime.value = duration.value;
      stop();
    }
  }
}

function startAnimFrame() {
  function tick() {
    if (!isPlaying.value) return;
    updateCurrentTime();
    animFrameId = requestAnimationFrame(tick);
  }
  animFrameId = requestAnimationFrame(tick);
}

function toggleMute(trackIndex) {
  trackMutes.value[trackIndex] = !trackMutes.value[trackIndex];
  if (gainNodes[trackIndex]) {
    const hasSolo = trackSolos.value.some((s) => s);
    const muted = hasSolo ? !trackSolos.value[trackIndex] : trackMutes.value[trackIndex];
    gainNodes[trackIndex].gain.value = muted ? 0.0 : trackVolumes.value[trackIndex];
  }
}

function toggleSolo(trackIndex) {
  trackSolos.value[trackIndex] = !trackSolos.value[trackIndex];
  const hasSolo = trackSolos.value.some((s) => s);
  for (let i = 0; i < trackCount.value; i++) {
    if (gainNodes[i]) {
      const muted = hasSolo ? !trackSolos.value[i] : trackMutes.value[i];
      gainNodes[i].gain.value = muted ? 0.0 : trackVolumes.value[i];
    }
  }
}

function setVolume(trackIndex, vol) {
  trackVolumes.value[trackIndex] = vol;
  if (gainNodes[trackIndex]) {
    const hasSolo = trackSolos.value.some((s) => s);
    const muted = hasSolo ? !trackSolos.value[trackIndex] : trackMutes.value[trackIndex];
    gainNodes[trackIndex].gain.value = muted ? 0.0 : vol;
  }
}

function cleanup() {
  stop();
  if (audioCtx) {
    audioCtx.close();
    audioCtx = null;
  }
  ready = false;
}

function formatTime(seconds) {
  if (!isFinite(seconds) || seconds < 0) return "00:00.0";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${s.toFixed(1).padStart(4, "0")}`;
}

export function usePlayback() {
  return {
    isPlaying,
    isPreparing,
    currentTime: computed(() => currentTime.value),
    duration: computed(() => duration.value),
    sampleRate: computed(() => sampleRate.value),
    trackCount: computed(() => trackCount.value),
    trackMutes: computed(() => trackMutes.value),
    trackSolos: computed(() => trackSolos.value),
    trackVolumes: computed(() => trackVolumes.value),
    prepare,
    play,
    stop,
    pause,
    seek,
    toggleMute,
    toggleSolo,
    setVolume,
    cleanup,
    formatTime,
  };
}
