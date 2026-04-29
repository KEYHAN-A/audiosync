/**
 * useSettings — Persistent app settings via Tauri Store.
 *
 * Follows the same pattern as useAuth.js for store access.
 * Currently stores: onboarding completion flag.
 */

import { ref } from "vue";
import { Store } from "@tauri-apps/plugin-store";

let store = null;

async function getStore() {
  if (!store) {
    store = await Store.load("settings.json");
  }
  return store;
}

const hasCompletedOnboarding = ref(false);

async function loadSettings() {
  try {
    const s = await getStore();
    const value = await s.get("onboarding_complete");
    hasCompletedOnboarding.value = value === true;
  } catch (e) {
    console.warn("Failed to load settings:", e);
  }
}

async function markOnboardingComplete() {
  try {
    const s = await getStore();
    await s.set("onboarding_complete", true);
    await s.save();
    hasCompletedOnboarding.value = true;
  } catch (e) {
    console.warn("Failed to save onboarding state:", e);
    hasCompletedOnboarding.value = true;
  }
}

export function useSettings() {
  return {
    hasCompletedOnboarding,
    loadSettings,
    markOnboardingComplete,
  };
}
