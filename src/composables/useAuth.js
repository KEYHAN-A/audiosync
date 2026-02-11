/**
 * useAuth — Device code authentication flow for AudioSync Pro.
 *
 * Uses the api.keyhan.info device auth endpoints:
 *   POST /auth/device/code   → get device_code + user_code
 *   POST /auth/device/token  → poll until authorized, receive JWT
 *   GET  /auth/me             → get current user info
 */

import { reactive, computed } from "vue";
import { Store } from "@tauri-apps/plugin-store";
import { open as openUrl } from "@tauri-apps/plugin-shell";

const API_BASE = "https://api.keyhan.info";

// Persistent store for auth token
let store = null;

async function getStore() {
  if (!store) {
    store = await Store.load("auth.json");
  }
  return store;
}

// ---------------------------------------------------------------------------
//  Singleton state
// ---------------------------------------------------------------------------

const state = reactive({
  user: null,
  token: null,
  isLoading: false,

  // Device flow state
  userCode: null,
  verificationUri: null,
  deviceFlowActive: false,
  deviceFlowError: null,
});

const isLoggedIn = computed(() => !!state.token && !!state.user);

// ---------------------------------------------------------------------------
//  API helpers
// ---------------------------------------------------------------------------

async function apiFetch(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...options.headers };
  if (state.token) {
    headers["Authorization"] = `Bearer ${state.token}`;
  }
  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  return res.json();
}

// ---------------------------------------------------------------------------
//  Auth actions
// ---------------------------------------------------------------------------

/** Load saved token on app start */
async function initAuth() {
  try {
    const s = await getStore();
    const token = await s.get("token");
    if (token) {
      state.token = token;
      await refreshUser();
    }
  } catch (e) {
    console.warn("Failed to load auth state:", e);
  }
}

/** Get current user info from the server */
async function refreshUser() {
  if (!state.token) return null;
  try {
    const data = await apiFetch("/auth/me");
    if (data.success && data.user) {
      state.user = data.user;
      return data.user;
    } else {
      // Token invalid
      await logout();
      return null;
    }
  } catch {
    return null;
  }
}

/** Start device code login flow */
async function startDeviceLogin() {
  state.deviceFlowActive = true;
  state.deviceFlowError = null;
  state.userCode = null;

  try {
    const data = await apiFetch("/auth/device/code", {
      method: "POST",
      body: JSON.stringify({ client_info: "AudioSync Pro Desktop" }),
    });

    if (!data.success) {
      state.deviceFlowError = data.error || "Failed to start login";
      state.deviceFlowActive = false;
      return;
    }

    state.userCode = data.user_code;
    state.verificationUri = data.verification_uri;

    // Open browser for verification
    const verifyUrl = `${data.verification_uri}?code=${data.user_code}`;
    try {
      await openUrl(verifyUrl);
    } catch {
      // If shell open fails, user can manually navigate
      console.warn("Could not open browser automatically");
    }

    // Start polling for token
    await pollForToken(data.device_code, data.expires_in, data.interval);
  } catch (e) {
    state.deviceFlowError = "Connection failed: " + e.message;
    state.deviceFlowActive = false;
  }
}

/** Poll the device token endpoint until authorized or expired */
async function pollForToken(deviceCode, expiresIn, interval) {
  const maxAttempts = Math.floor(expiresIn / interval);
  let attempts = 0;

  const poll = () =>
    new Promise((resolve) => {
      const timer = setInterval(async () => {
        attempts++;
        if (attempts > maxAttempts || !state.deviceFlowActive) {
          clearInterval(timer);
          if (state.deviceFlowActive) {
            state.deviceFlowError = "Login timed out. Please try again.";
            state.deviceFlowActive = false;
          }
          resolve(false);
          return;
        }

        try {
          const data = await apiFetch("/auth/device/token", {
            method: "POST",
            body: JSON.stringify({ device_code: deviceCode }),
          });

          if (data.success && data.token) {
            clearInterval(timer);

            // Save token
            state.token = data.token;
            state.user = data.user;
            state.deviceFlowActive = false;
            state.userCode = null;

            const s = await getStore();
            await s.set("token", data.token);
            await s.save();

            resolve(true);
            return;
          }

          if (data.error === "expired") {
            clearInterval(timer);
            state.deviceFlowError = "Login expired. Please try again.";
            state.deviceFlowActive = false;
            resolve(false);
            return;
          }

          // authorization_pending — keep polling
        } catch {
          // Network error, keep trying
        }
      }, interval * 1000);
    });

  return poll();
}

/** Cancel an in-progress device flow */
function cancelDeviceLogin() {
  state.deviceFlowActive = false;
  state.userCode = null;
  state.deviceFlowError = null;
}

/** Log out and clear stored token */
async function logout() {
  state.token = null;
  state.user = null;
  state.userCode = null;
  state.deviceFlowActive = false;

  try {
    const s = await getStore();
    await s.delete("token");
    await s.save();
  } catch (e) {
    console.warn("Failed to clear auth store:", e);
  }
}

// ---------------------------------------------------------------------------
//  Export
// ---------------------------------------------------------------------------

export function useAuth() {
  return {
    state,
    isLoggedIn,
    initAuth,
    refreshUser,
    startDeviceLogin,
    cancelDeviceLogin,
    logout,
    apiFetch,
    API_BASE,
  };
}
