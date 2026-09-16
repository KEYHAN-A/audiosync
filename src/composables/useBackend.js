/**
 * useBackend — Abstraction over Tauri IPC vs WASM engine.
 *
 * Detects the runtime environment and provides a unified async API
 * that the rest of the app uses without knowing whether it's talking
 * to a Rust Tauri backend or a WASM module in the browser.
 */

const IS_TAURI = typeof window !== "undefined" && window.__TAURI_INTERNALS__ !== undefined;

let wasmEngine = null;
let wasmReady = false;

async function initWasm() {
  if (wasmReady) return;
  const module = await import("../../audiosync-wasm/pkg/audiosync_wasm.js");
  wasmEngine = new module.WasmSyncEngine();
  wasmReady = true;
}

// ---------------------------------------------------------------------------
//  Unified backend API
// ---------------------------------------------------------------------------

export function useBackend() {
  return {
    isTauri: IS_TAURI,
    supportsVideo: IS_TAURI,

    async getVersion() {
      if (IS_TAURI) {
        const { invoke } = await import("@tauri-apps/api/core");
        return invoke("get_version");
      }
      await initWasm();
      return wasmEngine.version();
    },

    async loadClipFromBytes(name, data) {
      if (IS_TAURI) {
        throw new Error("Use importFiles/importPaths in Tauri mode");
      }
      await initWasm();
      const json = wasmEngine.load_clip_from_bytes(name, data);
      return JSON.parse(json);
    },

    async getTracks() {
      if (IS_TAURI) {
        const { invoke } = await import("@tauri-apps/api/core");
        return invoke("get_tracks");
      }
      await initWasm();
      const json = wasmEngine.get_tracks();
      return JSON.parse(json);
    },

    async analyze() {
      if (IS_TAURI) {
        const { invoke } = await import("@tauri-apps/api/core");
        return invoke("run_analysis", { maxOffsetS: null });
      }
      await initWasm();
      const json = wasmEngine.analyze();
      return JSON.parse(json);
    },

    async reset() {
      if (!IS_TAURI && wasmEngine) {
        wasmEngine.reset();
      }
    },

    get engine() {
      return wasmEngine;
    },
  };
}
