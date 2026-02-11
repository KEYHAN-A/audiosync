<script setup>
import { onMounted, onUnmounted, ref, computed } from "vue";
import { listen } from "@tauri-apps/api/event";
import { getCurrentWebviewWindow } from "@tauri-apps/api/webviewWindow";
import { useAudioSync } from "../composables/useAudioSync.js";
import { useAuth } from "../composables/useAuth.js";
import { useToast } from "../composables/useToast.js";
import WorkflowBar from "./WorkflowBar.vue";
import TrackPanel from "./TrackPanel.vue";
import WaveformCanvas from "./WaveformCanvas.vue";
import ResizeSplitter from "./ResizeSplitter.vue";
import ProcessingDialog from "./ProcessingDialog.vue";
import ExportDialog from "./ExportDialog.vue";
import AboutDialog from "./AboutDialog.vue";
import DriftFixDialog from "./DriftFixDialog.vue";
import LoginDialog from "./LoginDialog.vue";
import CloudProjectsDialog from "./CloudProjectsDialog.vue";
import ShareDialog from "./ShareDialog.vue";
import ToastNotification from "./ToastNotification.vue";

const {
  state,
  totalClips,
  isAnalyzed,
  timelineDuration,
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
  saveProject,
  loadProject,
  clearError,
  setupListeners,
  teardownListeners,
} = useAudioSync();

const { showToast } = useToast();

const { state: authState, isLoggedIn, initAuth } = useAuth();

// Dialog visibility
const showExportDialog = ref(false);
const showAboutDialog = ref(false);
const showDriftDialog = ref(false);
const showLoginDialog = ref(false);
const showCloudDialog = ref(false);
const showShareDialog = ref(false);

// Drag-and-drop
const isDragOver = ref(false);

// Menu event listener
let unlistenMenu = null;
let unlistenDragDrop = null;

// ---------------------------------------------------------------------------
//  Lifecycle
// ---------------------------------------------------------------------------

onMounted(async () => {
  await setupListeners();
  await fetchVersion();
  await initAuth();

  // Listen for native menu events from Rust
  unlistenMenu = await listen("menu-event", (event) => {
    handleMenuEvent(event.payload);
  });

  // Keyboard shortcuts
  window.addEventListener("keydown", handleKeydown);

  // Tauri v2 native drag-drop
  const webview = getCurrentWebviewWindow();
  unlistenDragDrop = await webview.onDragDropEvent((event) => {
    if (event.payload.type === "over" || event.payload.type === "enter") {
      isDragOver.value = true;
    } else if (event.payload.type === "leave") {
      isDragOver.value = false;
    } else if (event.payload.type === "drop") {
      isDragOver.value = false;
      const paths = event.payload.paths;
      if (paths && paths.length > 0) {
        importPaths(paths).then(() => {
          showToast(`Imported ${paths.length} file(s)`, "success");
        });
      }
    }
  });
});

onUnmounted(() => {
  teardownListeners();
  if (unlistenMenu) unlistenMenu();
  if (unlistenDragDrop) unlistenDragDrop();
  window.removeEventListener("keydown", handleKeydown);
});

// ---------------------------------------------------------------------------
//  Menu events from Rust
// ---------------------------------------------------------------------------

function handleMenuEvent(id) {
  switch (id) {
    case "import":
      importFiles();
      break;
    case "open-project":
      loadProject();
      break;
    case "save-project":
      saveProject();
      break;
    case "export":
      if (isAnalyzed.value) showExportDialog.value = true;
      else showToast("Run analysis first", "warning");
      break;
    case "analyze":
      handleAnalyze();
      break;
    case "drift-tool":
      showDriftDialog.value = true;
      break;
    case "about":
      showAboutDialog.value = true;
      break;
    default:
      break;
  }
}

// ---------------------------------------------------------------------------
//  Keyboard shortcuts
// ---------------------------------------------------------------------------

function handleKeydown(e) {
  const meta = e.metaKey || e.ctrlKey;

  if (meta && e.key === "o" && !e.shiftKey) {
    e.preventDefault();
    importFiles();
  } else if (meta && e.shiftKey && (e.key === "O" || e.key === "o")) {
    e.preventDefault();
    loadProject();
  } else if (meta && e.key === "s") {
    e.preventDefault();
    saveProject();
  } else if (meta && e.key === "r" && !state.processing && totalClips.value > 0) {
    e.preventDefault();
    handleAnalyze();
  } else if (meta && e.key === "e" && isAnalyzed.value) {
    e.preventDefault();
    showExportDialog.value = true;
  } else if (meta && e.key === "d") {
    e.preventDefault();
    showDriftDialog.value = true;
  } else if (e.key === "Escape") {
    if (state.processing) cancelOperation();
    else if (showExportDialog.value) showExportDialog.value = false;
    else if (showAboutDialog.value) showAboutDialog.value = false;
    else if (showDriftDialog.value) showDriftDialog.value = false;
    else if (showLoginDialog.value) showLoginDialog.value = false;
    else if (showCloudDialog.value) showCloudDialog.value = false;
    else if (showShareDialog.value) showShareDialog.value = false;
  }
}

// ---------------------------------------------------------------------------
//  Workflow actions
// ---------------------------------------------------------------------------

async function handleAnalyze() {
  if (totalClips.value === 0 || state.processing) return;
  await runAnalysis();
  if (isAnalyzed.value) {
    showToast("Analysis complete", "success");
  }
}

async function handleExport(config) {
  showExportDialog.value = false;
  const files = await runSyncAndExport(config);
  if (files && files.length > 0) {
    showToast(`Exported ${files.length} file(s)`, "success");
  }
}

function handleOpenExport() {
  if (isAnalyzed.value) {
    showExportDialog.value = true;
  }
}

/** Handle loading a project from cloud */
function handleCloudLoad(projectData) {
  if (projectData.tracks) {
    state.tracks = projectData.tracks;
    state.analysisResult = projectData.analysisResult || null;
    state.currentStep = state.analysisResult ? 2 : totalClips.value > 0 ? 1 : 0;
    state.statusMessage = "Project loaded from cloud";
    showToast("Project loaded from cloud", "success");
  }
}

// ---------------------------------------------------------------------------
//  Computed
// ---------------------------------------------------------------------------

const versionLabel = computed(
  () => `AudioSync Pro v${state.appVersion || "3.0.0"}`
);
</script>

<template>
  <div class="app-shell" :class="{ 'drag-over': isDragOver }">
    <!-- Background -->
    <div class="bg-grid"></div>
    <div class="glow-orb glow-orb-cyan orb-1"></div>
    <div class="glow-orb glow-orb-purple orb-2"></div>

    <!-- Drag overlay -->
    <Transition name="fade">
      <div v-if="isDragOver" class="drag-overlay">
        <div class="drag-content">
          <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M12 16v-8m0 0l-3 3m3-3l3 3M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5" />
          </svg>
          <p>Drop audio/video files to import</p>
        </div>
      </div>
    </Transition>

    <!-- Main content -->
    <div class="app-content">
      <WorkflowBar
        :currentStep="state.currentStep"
        :canAnalyze="totalClips > 0 && !state.processing"
        :canExport="isAnalyzed && !state.processing"
        @analyze="handleAnalyze"
        @export="handleOpenExport"
      />

      <div class="toolbar">
        <div class="toolbar-group">
          <button class="btn btn-primary btn-sm" @click="importFiles" :disabled="state.processing">
            <span class="btn-icon">+</span> Import Files
          </button>
          <button class="btn btn-ghost btn-sm" @click="loadProject" :disabled="state.processing">
            Open Project
          </button>
          <button
            class="btn btn-ghost btn-sm"
            @click="saveProject"
            :disabled="state.tracks.length === 0"
          >
            Save Project
          </button>
          <button
            v-if="isLoggedIn"
            class="btn btn-ghost btn-sm"
            @click="showCloudDialog = true"
            title="Cloud Projects"
          >
            Cloud
          </button>
        </div>
        <div class="toolbar-group">
          <button
            class="btn btn-ghost btn-sm"
            @click="showDriftDialog = true"
            title="Drift Measurement Tool (Cmd+D)"
          >
            Drift Tool
          </button>
          <button
            v-if="isLoggedIn && isAnalyzed"
            class="btn btn-ghost btn-sm"
            @click="showShareDialog = true"
            title="Share Timeline"
          >
            Share
          </button>
          <button
            class="btn btn-accent btn-sm"
            @click="handleAnalyze"
            :disabled="totalClips === 0 || state.processing"
          >
            Analyze
          </button>
          <button
            class="btn btn-success btn-sm"
            @click="handleOpenExport"
            :disabled="!isAnalyzed || state.processing"
          >
            Export
          </button>
          <button
            class="btn btn-user btn-sm"
            @click="showLoginDialog = true"
            :title="isLoggedIn ? authState.user?.email : 'Sign In'"
          >
            <img
              v-if="isLoggedIn && authState.user?.picture"
              :src="authState.user.picture"
              class="toolbar-avatar"
              referrerpolicy="no-referrer"
            />
            <template v-else>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z" />
              </svg>
            </template>
          </button>
        </div>
      </div>

      <ResizeSplitter :initialWidth="340" :minWidth="240" :maxWidth="550">
        <template #left>
          <TrackPanel
            :tracks="state.tracks"
            :processing="state.processing"
            @addTrack="createTrack"
            @addFiles="addFilesToTrack"
            @removeTrack="removeTrack"
            @removeClip="removeClip"
            @importFiles="importFiles"
          />
        </template>
        <template #right>
          <WaveformCanvas
            :tracks="state.tracks"
            :analysisResult="state.analysisResult"
            :timelineDuration="timelineDuration"
          />
        </template>
      </ResizeSplitter>

      <div class="status-bar">
        <span class="status-text">{{ versionLabel }}</span>
        <span v-if="state.lastError" class="status-text status-error" @click="clearError">
          {{ state.lastError }}
        </span>
        <span v-else class="status-text status-dim">{{ state.statusMessage }}</span>
        <span v-if="totalClips > 0" class="status-text status-dim">
          {{ state.tracks.length }} tracks / {{ totalClips }} clips
          <template v-if="timelineDuration > 0">
            / {{ timelineDuration.toFixed(1) }}s
          </template>
        </span>
      </div>
    </div>

    <!-- Dialogs -->
    <ProcessingDialog
      :visible="state.processing"
      :title="state.processingTitle"
      :step="state.processingStep"
      :total="state.processingTotal"
      :message="state.processingMessage"
      @cancel="cancelOperation"
    />

    <ExportDialog
      :visible="showExportDialog"
      :tracks="state.tracks"
      @close="showExportDialog = false"
      @export="handleExport"
    />

    <AboutDialog
      :visible="showAboutDialog"
      :version="state.appVersion"
      @close="showAboutDialog = false"
    />

    <DriftFixDialog
      :visible="showDriftDialog"
      @close="showDriftDialog = false"
    />

    <LoginDialog
      :visible="showLoginDialog"
      @close="showLoginDialog = false"
    />

    <CloudProjectsDialog
      :visible="showCloudDialog"
      :tracks="state.tracks"
      :analysisResult="state.analysisResult"
      @close="showCloudDialog = false"
      @loadProject="handleCloudLoad"
    />

    <ShareDialog
      :visible="showShareDialog"
      :tracks="state.tracks"
      :analysisResult="state.analysisResult"
      @close="showShareDialog = false"
    />

    <!-- Toast notifications -->
    <ToastNotification />
  </div>
</template>

<style scoped>
.app-shell {
  width: 100vw;
  height: 100vh;
  position: relative;
  overflow: hidden;
  background-color: var(--navy-deep);
  transition: border-color 0.2s ease;
}

.app-shell.drag-over {
  border: 2px solid var(--cyan);
}

.app-content {
  position: relative;
  z-index: 1;
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background-color: var(--bg-panel);
  border-bottom: 1px solid var(--border-subtle);
  gap: 8px;
}

.toolbar-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.btn-icon {
  font-weight: 700;
  margin-right: 2px;
}

.status-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 16px;
  background-color: var(--bg-panel);
  border-top: 1px solid var(--border-subtle);
  font-size: 11px;
  gap: 16px;
}

.status-text {
  color: var(--text-dim);
}

.status-dim {
  opacity: 0.6;
}

.status-error {
  color: var(--danger);
  opacity: 1;
  cursor: pointer;
}

.status-error:hover {
  text-decoration: underline;
}

/* Glow orb positions */
.orb-1 { width: 500px; height: 500px; top: -100px; right: -100px; opacity: 0.12; }
.orb-2 { width: 400px; height: 400px; bottom: 50px; left: -150px; opacity: 0.08; }

/* Drag overlay */
.drag-overlay {
  position: fixed;
  inset: 0;
  z-index: 100;
  background: rgba(6, 12, 28, 0.85);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
}

.drag-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: var(--cyan);
  text-align: center;
}

.drag-content p {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-bright);
}

/* Extra button styles */
.btn-success {
  background: linear-gradient(135deg, #059669, #10b981);
  color: white;
  border: none;
}
.btn-success:hover:not(:disabled) {
  box-shadow: 0 0 16px rgba(16, 185, 129, 0.3);
}
.btn-success:disabled {
  background: var(--border-subtle);
  color: var(--text-muted);
  box-shadow: none;
}

/* User button */
.btn-user {
  padding: 3px 6px;
  border: 1px solid var(--border-subtle);
  border-radius: 50%;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
  min-width: 28px;
  height: 28px;
}
.btn-user:hover {
  border-color: var(--cyan);
  color: var(--cyan);
}
.toolbar-avatar {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  object-fit: cover;
}
</style>
