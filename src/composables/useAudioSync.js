/**
 * useAudioSync — Central state management and Tauri IPC bridge.
 *
 * Provides reactive state and async methods for the entire app workflow:
 *   Import → Analyze → Sync/Export
 *
 * All Tauri `invoke()` calls go through this composable so components
 * stay decoupled from the backend.
 */

import { reactive, computed, ref } from "vue";
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { open, save } from "@tauri-apps/plugin-dialog";

// ---------------------------------------------------------------------------
//  Singleton reactive state
// ---------------------------------------------------------------------------

const state = reactive({
  tracks: [],
  analysisResult: null,
  appVersion: "",

  // Workflow step: 0 = Import, 1 = Analyze, 2 = Export
  currentStep: 0,

  // Processing state
  processing: false,
  processingTitle: "",
  processingStep: 0,
  processingTotal: 0,
  processingMessage: "",

  // Status bar
  statusMessage: "Ready",

  // Errors / warnings
  lastError: null,
  warnings: [],
});

// ---------------------------------------------------------------------------
//  Computed helpers
// ---------------------------------------------------------------------------

const totalClips = computed(() =>
  state.tracks.reduce((n, t) => n + (t.clips?.length || 0), 0)
);

const isAnalyzed = computed(() => state.analysisResult !== null);

const referenceTrack = computed(() =>
  state.tracks.find((t) => t.is_reference)
);

const timelineDuration = computed(
  () => state.analysisResult?.total_timeline_s || 0
);

// ---------------------------------------------------------------------------
//  Tauri IPC wrappers
// ---------------------------------------------------------------------------

/** Fetch the app version from Rust */
async function fetchVersion() {
  try {
    state.appVersion = await invoke("get_version");
  } catch (e) {
    console.warn("Failed to get version:", e);
    state.appVersion = "3.0.0";
  }
}

/** Open file dialog and import files */
async function importFiles() {
  try {
    const selected = await open({
      multiple: true,
      title: "Import Audio/Video Files",
      filters: [
        {
          name: "Audio & Video",
          extensions: [
            "wav", "aiff", "aif", "flac", "mp3", "ogg", "opus",
            "mp4", "mov", "mkv", "avi", "webm", "mts", "m4v", "mxf",
          ],
        },
        { name: "All Files", extensions: ["*"] },
      ],
    });

    if (!selected || selected.length === 0) return;

    const paths = selected.map((f) => (typeof f === "string" ? f : f.path));
    await importPaths(paths);
  } catch (e) {
    setError("Import failed: " + e);
  }
}

/** Import files from paths (used by dialog and drag-drop) */
async function importPaths(paths) {
  if (!paths || paths.length === 0) return;

  state.processing = true;
  state.processingTitle = "Importing Files";
  state.processingStep = 0;
  state.processingTotal = paths.length;
  state.processingMessage = "Preparing...";
  state.lastError = null;

  try {
    const tracks = await invoke("import_files", { paths });
    state.tracks = tracks;
    state.analysisResult = null;
    state.currentStep = totalClips.value > 0 ? 1 : 0;
    state.statusMessage = `Imported ${totalClips.value} clips in ${state.tracks.length} tracks`;
  } catch (e) {
    setError("Import failed: " + e);
  } finally {
    state.processing = false;
  }
}

/** Add files to an existing track */
async function addFilesToTrack(trackIndex) {
  try {
    const selected = await open({
      multiple: true,
      title: "Add Files to Track",
      filters: [
        {
          name: "Audio & Video",
          extensions: [
            "wav", "aiff", "aif", "flac", "mp3", "ogg", "opus",
            "mp4", "mov", "mkv", "avi", "webm", "mts", "m4v", "mxf",
          ],
        },
      ],
    });

    if (!selected || selected.length === 0) return;

    const paths = selected.map((f) => (typeof f === "string" ? f : f.path));

    state.processing = true;
    state.processingTitle = "Adding Files";
    state.processingMessage = "Loading...";

    const tracks = await invoke("add_files_to_track", {
      trackIndex,
      paths,
    });
    state.tracks = tracks;
    state.analysisResult = null;
    state.statusMessage = `Added files to track`;
  } catch (e) {
    setError("Add files failed: " + e);
  } finally {
    state.processing = false;
  }
}

/** Create a new empty track */
async function createTrack(name) {
  try {
    const tracks = await invoke("create_track", {
      name: name || `Track ${state.tracks.length + 1}`,
    });
    state.tracks = tracks;
  } catch (e) {
    setError("Create track failed: " + e);
  }
}

/** Remove a track */
async function removeTrack(index) {
  try {
    const tracks = await invoke("remove_track", { index });
    state.tracks = tracks;
    state.analysisResult = null;
    if (totalClips.value === 0) state.currentStep = 0;
  } catch (e) {
    setError("Remove track failed: " + e);
  }
}

/** Remove a clip from a track */
async function removeClip(trackIndex, clipIndex) {
  try {
    const tracks = await invoke("remove_clip", { trackIndex, clipIndex });
    state.tracks = tracks;
    state.analysisResult = null;
  } catch (e) {
    setError("Remove clip failed: " + e);
  }
}

/** Run the analysis engine */
async function runAnalysis(maxOffsetS = null) {
  if (totalClips.value === 0) {
    setError("No clips to analyze. Import files first.");
    return;
  }

  state.processing = true;
  state.processingTitle = "Analyzing";
  state.processingStep = 0;
  state.processingTotal = totalClips.value + 4;
  state.processingMessage = "Starting analysis...";
  state.lastError = null;

  try {
    const result = await invoke("run_analysis", {
      maxOffsetS,
    });
    state.tracks = result.tracks;
    state.analysisResult = result.result;
    state.warnings = result.result.warnings || [];
    state.currentStep = 2;
    state.statusMessage = `Analysis complete — ${state.tracks.length} tracks, avg confidence ${result.result.avg_confidence.toFixed(1)}`;
  } catch (e) {
    if (String(e).includes("cancelled")) {
      state.statusMessage = "Analysis cancelled";
    } else {
      setError("Analysis failed: " + e);
    }
  } finally {
    state.processing = false;
  }
}

/** Run sync and export */
async function runSyncAndExport(exportConfig) {
  if (!state.analysisResult) {
    setError("Run analysis first.");
    return;
  }

  state.processing = true;
  state.processingTitle = "Syncing & Exporting";
  state.processingStep = 0;
  state.processingTotal = totalClips.value;
  state.processingMessage = "Starting sync...";
  state.lastError = null;

  try {
    const files = await invoke("run_sync_and_export", {
      exportConfig,
    });
    state.statusMessage = `Exported ${files.length} files`;
    return files;
  } catch (e) {
    if (String(e).includes("cancelled")) {
      state.statusMessage = "Export cancelled";
    } else {
      setError("Export failed: " + e);
    }
    return [];
  } finally {
    state.processing = false;
  }
}

/** Cancel the current operation */
async function cancelOperation() {
  try {
    await invoke("cancel_operation");
    state.statusMessage = "Cancelling...";
  } catch (e) {
    console.warn("Cancel failed:", e);
  }
}

/** Measure drift between two files */
async function measureDrift(referencePath, targetPath) {
  state.processing = true;
  state.processingTitle = "Measuring Drift";
  state.processingMessage = "Loading files...";

  try {
    const result = await invoke("measure_drift", {
      referencePath,
      targetPath,
    });
    return result;
  } catch (e) {
    setError("Drift measurement failed: " + e);
    return null;
  } finally {
    state.processing = false;
  }
}

/** Save project to file */
async function saveProject() {
  try {
    const path = await save({
      title: "Save Project",
      defaultPath: "project.audiosync.json",
      filters: [
        { name: "AudioSync Project", extensions: ["audiosync.json"] },
      ],
    });
    if (!path) return;

    await invoke("save_project", { path });
    state.statusMessage = `Project saved`;
  } catch (e) {
    setError("Save failed: " + e);
  }
}

/** Load project from file */
async function loadProject() {
  try {
    const selected = await open({
      title: "Open Project",
      filters: [
        { name: "AudioSync Project", extensions: ["audiosync.json", "json"] },
      ],
    });
    if (!selected) return;

    const path = typeof selected === "string" ? selected : selected.path;

    const result = await invoke("load_project", { path });
    state.tracks = result.tracks;
    state.analysisResult =
      result.result.total_timeline_samples > 0 ? result.result : null;
    state.currentStep = state.analysisResult ? 2 : totalClips.value > 0 ? 1 : 0;
    state.statusMessage = `Project loaded — ${state.tracks.length} tracks`;
  } catch (e) {
    setError("Load failed: " + e);
  }
}

// ---------------------------------------------------------------------------
//  Event listeners
// ---------------------------------------------------------------------------

let unlistenImport = null;
let unlistenAnalysis = null;
let unlistenSync = null;

async function setupListeners() {
  unlistenImport = await listen("import-progress", (event) => {
    state.processingStep = event.payload.step;
    state.processingTotal = event.payload.total;
    state.processingMessage = event.payload.message;
  });
  unlistenAnalysis = await listen("analysis-progress", (event) => {
    state.processingStep = event.payload.step;
    state.processingTotal = event.payload.total;
    state.processingMessage = event.payload.message;
  });
  unlistenSync = await listen("sync-progress", (event) => {
    state.processingStep = event.payload.step;
    state.processingTotal = event.payload.total;
    state.processingMessage = event.payload.message;
  });
}

function teardownListeners() {
  if (unlistenImport) unlistenImport();
  if (unlistenAnalysis) unlistenAnalysis();
  if (unlistenSync) unlistenSync();
}

// ---------------------------------------------------------------------------
//  Helpers
// ---------------------------------------------------------------------------

function setError(msg) {
  state.lastError = msg;
  state.statusMessage = msg;
  console.error(msg);
}

function clearError() {
  state.lastError = null;
}

// ---------------------------------------------------------------------------
//  Composable export
// ---------------------------------------------------------------------------

export function useAudioSync() {
  return {
    // State
    state,

    // Computed
    totalClips,
    isAnalyzed,
    referenceTrack,
    timelineDuration,

    // Actions
    fetchVersion,
    importFiles,
    importPaths,
    addFilesToTrack,
    createTrack,
    removeTrack,
    removeClip,
    runAnalysis,
    runSyncAndExport,
    cancelOperation,
    measureDrift,
    saveProject,
    loadProject,
    clearError,

    // Lifecycle
    setupListeners,
    teardownListeners,
  };
}
