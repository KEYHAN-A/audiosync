<script setup>
import { ref, onMounted, watch } from "vue";
import { useCloud } from "../composables/useCloud.js";
import { useAuth } from "../composables/useAuth.js";

const props = defineProps({
  visible: { type: Boolean, default: false },
  tracks: { type: Array, default: () => [] },
  analysisResult: { type: Object, default: null },
});

const emit = defineEmits(["close", "loadProject"]);

const { state: cloudState, listProjects, saveToCloud, deleteFromCloud, loadFromCloud } = useCloud();
const { isLoggedIn } = useAuth();

const saveName = ref("");
const saveDescription = ref("");
const showSaveForm = ref(false);
const confirmDeleteId = ref(null);

watch(
  () => props.visible,
  async (v) => {
    if (v && isLoggedIn.value) {
      await listProjects();
    }
  }
);

async function handleSave() {
  if (!saveName.value.trim()) return;
  const projectData = {
    tracks: props.tracks,
    analysisResult: props.analysisResult,
  };
  const result = await saveToCloud(saveName.value.trim(), saveDescription.value.trim(), projectData);
  if (result) {
    saveName.value = "";
    saveDescription.value = "";
    showSaveForm.value = false;
  }
}

async function handleLoad(id) {
  const project = await loadFromCloud(id);
  if (project && project.data) {
    emit("loadProject", project.data);
    emit("close");
  }
}

async function handleDelete(id) {
  await deleteFromCloud(id);
  confirmDeleteId.value = null;
}

function formatDate(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
</script>

<template>
  <Transition name="fade">
    <div v-if="visible" class="dialog-overlay" @click.self="emit('close')">
      <div class="dialog glass-card">
        <div class="dialog-header">
          <h3 class="dialog-title">Cloud Projects</h3>
          <button class="close-btn" @click="emit('close')">&times;</button>
        </div>

        <!-- Save current project -->
        <div class="save-section">
          <button
            v-if="!showSaveForm"
            class="btn btn-primary btn-block"
            @click="showSaveForm = true"
            :disabled="!tracks.length"
          >
            Save Current Project to Cloud
          </button>

          <div v-else class="save-form">
            <input
              v-model="saveName"
              class="form-input"
              type="text"
              placeholder="Project name"
              autofocus
              @keyup.enter="handleSave"
            />
            <input
              v-model="saveDescription"
              class="form-input"
              type="text"
              placeholder="Description (optional)"
            />
            <div class="save-actions">
              <button class="btn btn-ghost btn-sm" @click="showSaveForm = false">Cancel</button>
              <button
                class="btn btn-primary btn-sm"
                @click="handleSave"
                :disabled="!saveName.trim() || cloudState.isLoading"
              >
                {{ cloudState.isLoading ? "Saving..." : "Save" }}
              </button>
            </div>
          </div>
        </div>

        <!-- Divider -->
        <div class="divider"></div>

        <!-- Project list -->
        <div class="project-list">
          <div v-if="cloudState.isLoading && !cloudState.projects.length" class="loading-state">
            <div class="spinner"></div>
            <span>Loading projects...</span>
          </div>

          <div v-else-if="!cloudState.projects.length" class="empty-state">
            <p>No cloud projects yet</p>
            <p class="empty-hint">Save a project above to get started</p>
          </div>

          <div
            v-for="project in cloudState.projects"
            :key="project.id"
            class="project-card"
          >
            <div class="project-info">
              <span class="project-name">{{ project.name }}</span>
              <span v-if="project.description" class="project-desc">{{ project.description }}</span>
              <span class="project-date">{{ formatDate(project.updated_at || project.created_at) }}</span>
            </div>
            <div class="project-actions">
              <button class="btn btn-accent btn-xs" @click="handleLoad(project.id)" :disabled="cloudState.isLoading">
                Load
              </button>
              <button
                v-if="confirmDeleteId !== project.id"
                class="btn btn-ghost btn-xs btn-danger-hover"
                @click="confirmDeleteId = project.id"
              >
                Delete
              </button>
              <button
                v-else
                class="btn btn-danger btn-xs"
                @click="handleDelete(project.id)"
                :disabled="cloudState.isLoading"
              >
                Confirm
              </button>
            </div>
          </div>
        </div>

        <!-- Error -->
        <p v-if="cloudState.error" class="error-msg">{{ cloudState.error }}</p>
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
  width: 480px;
  max-width: 90vw;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
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

.save-section {
  margin-bottom: 0;
}

.save-form {
  display: flex;
  flex-direction: column;
  gap: 8px;
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

.save-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.divider {
  height: 1px;
  background: var(--border-subtle, rgba(56, 189, 248, 0.08));
  margin: 16px 0;
}

.project-list {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 100px;
  max-height: 400px;
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 32px 16px;
  gap: 8px;
  color: var(--text-muted);
  font-size: 13px;
}

.empty-hint {
  font-size: 11px;
  opacity: 0.6;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(56, 189, 248, 0.2);
  border-top-color: var(--cyan, #38bdf8);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.project-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 14px;
  border: 1px solid var(--border-subtle, rgba(56, 189, 248, 0.08));
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  transition: all 0.15s ease;
}

.project-card:hover {
  border-color: rgba(56, 189, 248, 0.15);
  background: rgba(56, 189, 248, 0.03);
}

.project-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.project-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-bright);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.project-desc {
  font-size: 11px;
  color: var(--text-dim);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.project-date {
  font-size: 10px;
  color: var(--text-muted);
}

.project-actions {
  display: flex;
  gap: 6px;
  flex-shrink: 0;
}

.btn-xs {
  padding: 4px 10px;
  font-size: 11px;
  border-radius: 6px;
}

.btn-danger-hover:hover {
  color: #ef4444 !important;
  border-color: #ef4444 !important;
}

.btn-danger {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
  border: 1px solid rgba(239, 68, 68, 0.3);
}

.btn-block {
  width: 100%;
}

.error-msg {
  margin-top: 12px;
  font-size: 12px;
  color: #ef4444;
  text-align: center;
}
</style>
