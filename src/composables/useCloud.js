/**
 * useCloud — Cloud project CRUD and timeline sharing.
 *
 * Endpoints on api.keyhan.info:
 *   GET    /audiosync/projects         → list user projects
 *   POST   /audiosync/projects         → create project
 *   GET    /audiosync/projects/:id     → get project with data
 *   PUT    /audiosync/projects/:id     → update project
 *   DELETE /audiosync/projects/:id     → delete project
 *   POST   /audiosync/share            → create share link
 */

import { reactive } from "vue";
import { useAuth } from "./useAuth.js";

const { apiFetch, isLoggedIn } = useAuth();

// ---------------------------------------------------------------------------
//  State
// ---------------------------------------------------------------------------

const state = reactive({
  projects: [],
  isLoading: false,
  error: null,
});

// ---------------------------------------------------------------------------
//  Project CRUD
// ---------------------------------------------------------------------------

/** List all cloud projects for the authenticated user */
async function listProjects() {
  if (!isLoggedIn.value) return [];

  state.isLoading = true;
  state.error = null;
  try {
    const data = await apiFetch("/audiosync/projects");
    if (data.success) {
      state.projects = data.projects || [];
      return state.projects;
    } else {
      state.error = data.error || "Failed to list projects";
      return [];
    }
  } catch (e) {
    state.error = "Connection failed: " + e.message;
    return [];
  } finally {
    state.isLoading = false;
  }
}

/** Save a project to the cloud */
async function saveToCloud(name, description, projectData) {
  if (!isLoggedIn.value) return null;

  state.isLoading = true;
  state.error = null;
  try {
    const data = await apiFetch("/audiosync/projects", {
      method: "POST",
      body: JSON.stringify({
        name,
        description: description || "",
        data: projectData,
      }),
    });
    if (data.success) {
      // Refresh project list
      await listProjects();
      return data.project;
    } else {
      state.error = data.error || "Failed to save project";
      return null;
    }
  } catch (e) {
    state.error = "Connection failed: " + e.message;
    return null;
  } finally {
    state.isLoading = false;
  }
}

/** Update an existing cloud project */
async function updateCloud(id, name, description, projectData) {
  if (!isLoggedIn.value) return null;

  state.isLoading = true;
  state.error = null;
  try {
    const body = {};
    if (name !== undefined) body.name = name;
    if (description !== undefined) body.description = description;
    if (projectData !== undefined) body.data = projectData;

    const data = await apiFetch(`/audiosync/projects/${id}`, {
      method: "PUT",
      body: JSON.stringify(body),
    });
    if (data.success) {
      await listProjects();
      return data.project;
    } else {
      state.error = data.error || "Failed to update project";
      return null;
    }
  } catch (e) {
    state.error = "Connection failed: " + e.message;
    return null;
  } finally {
    state.isLoading = false;
  }
}

/** Load a project from the cloud */
async function loadFromCloud(id) {
  if (!isLoggedIn.value) return null;

  state.isLoading = true;
  state.error = null;
  try {
    const data = await apiFetch(`/audiosync/projects/${id}`);
    if (data.success) {
      return data.project;
    } else {
      state.error = data.error || "Failed to load project";
      return null;
    }
  } catch (e) {
    state.error = "Connection failed: " + e.message;
    return null;
  } finally {
    state.isLoading = false;
  }
}

/** Delete a project from the cloud */
async function deleteFromCloud(id) {
  if (!isLoggedIn.value) return false;

  state.isLoading = true;
  state.error = null;
  try {
    const data = await apiFetch(`/audiosync/projects/${id}`, {
      method: "DELETE",
    });
    if (data.success) {
      state.projects = state.projects.filter((p) => p.id !== id);
      return true;
    } else {
      state.error = data.error || "Failed to delete project";
      return false;
    }
  } catch (e) {
    state.error = "Connection failed: " + e.message;
    return false;
  } finally {
    state.isLoading = false;
  }
}

// ---------------------------------------------------------------------------
//  Timeline sharing
// ---------------------------------------------------------------------------

/** Share a timeline — returns the share URL */
async function shareTimeline(projectName, timelineData) {
  if (!isLoggedIn.value) return null;

  state.isLoading = true;
  state.error = null;
  try {
    const data = await apiFetch("/audiosync/share", {
      method: "POST",
      body: JSON.stringify({
        name: projectName,
        data: timelineData,
      }),
    });
    if (data.success) {
      return data.share_url;
    } else {
      state.error = data.error || "Failed to share timeline";
      return null;
    }
  } catch (e) {
    state.error = "Connection failed: " + e.message;
    return null;
  } finally {
    state.isLoading = false;
  }
}

// ---------------------------------------------------------------------------
//  Export
// ---------------------------------------------------------------------------

export function useCloud() {
  return {
    state,
    listProjects,
    saveToCloud,
    updateCloud,
    loadFromCloud,
    deleteFromCloud,
    shareTimeline,
  };
}
