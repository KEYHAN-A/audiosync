# AudioSync Pro — Rust + Tauri v2 Port Plan

## Overview

Port AudioSync Pro from PyQt6 to Rust + Tauri v2 with Vue 3 frontend, while preserving the Python core as a standalone CLI option. Includes a Rust CLI for headless/server use. Phased from development through production release.

---

## Why This Stack

- **Rust + Tauri v2** — Single ~15-30 MB binary per platform (vs ~150 MB PyInstaller), zero runtime deps, native performance for FFT
- **Vue 3 + Custom CSS** — Lightweight reactive framework, Composition API, no React/Tailwind dependency. Custom CSS replicates the website's gorgeous glassmorphism design
- **Cargo Workspace** — Shared `audiosync-core` library crate between Tauri desktop app and Rust CLI binary
- **Python preserved** — Moved to `python/` subdirectory with its own CLI, documented as alternative for Python users

---

## Architecture

```
                    ┌─────────────────────────────────────┐
                    │    Frontend — Vue 3 + Custom CSS     │
                    │                                      │
                    │  Vue 3 Composition API                │
                    │  Canvas Waveform Renderer             │
                    │  Glassmorphism Dark Navy CSS          │
                    │  CSS + Canvas Animations              │
                    └──────────────┬───────────────────────┘
                                   │ invoke()
                    ┌──────────────▼───────────────────────┐
                    │     Desktop App — Tauri v2            │
                    │                                      │
                    │  Tauri Command Handlers               │
                    │  Progress Event Streaming             │
                    └──────────────┬───────────────────────┘
                                   │
          ┌────────────────────────▼────────────────────────┐
          │          audiosync-core — Rust Library           │
          │                                                  │
          │  engine.rs     — FFT cross-correlation, drift    │
          │  audio_io.rs   — symphonia/hound, ffmpeg, cache  │
          │  models.rs     — Clip, Track, SyncResult structs │
          │  cloud.rs      — reqwest HTTP client             │
          │  project_io.rs — serde_json project files        │
          │  metadata.rs   — ffprobe subprocess              │
          │  grouping.rs   — Device auto-grouping            │
          │  timeline_export.rs — FCPXML/EDL generation      │
          └──────────┬─────────────────────┬────────────────┘
                     │                     │
        ┌────────────▼──────┐   ┌──────────▼──────────────┐
        │  audiosync-cli    │   │  python/ — Alternative   │
        │  Rust CLI Binary  │   │  Python CLI + Core       │
        │  (clap, JSON out) │   │  (original algorithm)    │
        └───────────────────┘   └─────────────────────────┘
```

---

## Project Structure

```
AudioSyncPro/
  Cargo.toml                        # Workspace root
  audiosync-core/                   # Shared Rust library crate
    Cargo.toml
    src/
      lib.rs
      engine.rs                     # FFT cross-correlation, drift, sync
      audio_io.rs                   # Load/export audio, cache, ffmpeg
      models.rs                     # Clip, Track, SyncResult, SyncConfig
      project_io.rs                 # JSON project serialization
      cloud.rs                      # Cloud API client (reqwest)
      grouping.rs                   # Auto-group files by device prefix
      metadata.rs                   # ffprobe metadata extraction
      timeline_export.rs            # FCPXML/EDL generation
  audiosync-cli/                    # Standalone Rust CLI binary
    Cargo.toml                      # depends on audiosync-core
    src/
      main.rs                       # clap CLI, JSON output mode
  src-tauri/                        # Tauri v2 desktop app
    Cargo.toml                      # depends on audiosync-core + tauri
    src/
      main.rs                       # Tauri entry point
      commands.rs                   # IPC command handlers
      state.rs                      # App state management
    tauri.conf.json
    icons/
  src/                              # Vue 3 frontend
    main.js
    App.vue
    components/
      MainLayout.vue
      WorkflowBar.vue
      TrackPanel.vue
      TrackCard.vue
      WaveformCanvas.vue            # Canvas 2D waveform renderer
      dialogs/
        ProcessingDialog.vue
        ExportDialog.vue
        DriftFixDialog.vue
        DeviceAuthDialog.vue
        CloudProjectsDialog.vue
        AboutDialog.vue
    composables/
      useAudioSync.js               # Tauri IPC wrapper
      useTheme.js                   # Reactive theme/colors
    styles/
      main.css                      # Full glassmorphism design system
      animations.css                # Waveform + UI animations
    assets/
  index.html
  vite.config.js
  package.json
  python/                           # Python alternative (preserved)
    core/                           # Original core/ moved here
      __init__.py
      engine.py
      audio_io.py
      models.py
      grouping.py
      metadata.py
      project_io.py
      timeline_export.py
      cloud.py
    cli.py                          # Python CLI entry point
    requirements.txt
    README.md
  website/                          # Marketing site (unchanged)
  AudioSync.js                      # Max for Live (unchanged)
  icon.icns
  icon.png
  LICENSE
  README.md                         # Updated with all three usage modes
```

---

## Python to Rust Mapping

| Python Module | Rust Crate/Module | Key Change |
|---|---|---|
| `core/engine.py` (845 lines) | `audiosync-core/src/engine.rs` | `scipy.signal.fftconvolve` → `rustfft`, `scipy.signal.resample` → `rubato`, `numpy` → `Vec<f32>` / `ndarray` |
| `core/audio_io.py` (675 lines) | `audiosync-core/src/audio_io.rs` | `soundfile` → `symphonia` (read) + `hound` (write), ffmpeg subprocess stays |
| `core/models.py` (157 lines) | `audiosync-core/src/models.rs` | Dataclasses → Rust structs with `serde` |
| `core/project_io.py` (194 lines) | `audiosync-core/src/project_io.rs` | `json` → `serde_json` |
| `core/cloud.py` (239 lines) | `audiosync-core/src/cloud.rs` | `urllib` → `reqwest`, `QSettings` → `tauri-plugin-store` |
| `core/grouping.py` (37 lines) | `audiosync-core/src/grouping.rs` | Direct port |
| `core/metadata.py` (101 lines) | `audiosync-core/src/metadata.rs` | Direct port, `std::process::Command` |
| `core/timeline_export.py` (239 lines) | `audiosync-core/src/timeline_export.rs` | Drop OTIO, use `quick-xml` for FCPXML |

---

## Key Rust Crates

- `rustfft` — FFT for cross-correlation
- `rubato` — High-quality audio resampling
- `symphonia` — Audio decoding (WAV, FLAC, AIFF, MP3, OGG)
- `hound` — WAV writing
- `ndarray` — N-dimensional arrays
- `reqwest` — Async HTTP client
- `serde` / `serde_json` — Serialization
- `dirs` — Platform-specific directories
- `clap` — CLI argument parsing
- `tauri` — Desktop app framework
- `tokio` — Async runtime
- `quick-xml` — FCPXML generation

## Key Frontend Dependencies

- `vue` (v3) — Composition API
- `@tauri-apps/api` — Tauri IPC bridge
- `@tauri-apps/plugin-dialog` — Native file dialogs
- `@tauri-apps/plugin-shell` — Shell integration
- `vite` + `@vitejs/plugin-vue` — Build tool

---

## Phase 0: Project Setup and Python Preservation

**Goal**: Restructure the repo so both Python and Rust coexist cleanly.

- [ ] Move `core/`, `app/`, `main.py`, `version.py`, `requirements.txt` into `python/` subdirectory
- [ ] Create `python/cli.py` — argparse CLI exposing analyze/sync/export pipeline
- [ ] Initialize Cargo workspace at repo root (`audiosync-core`, `audiosync-cli`)
- [ ] Initialize Tauri v2 project with Vue 3 + Vite (no Tailwind, no React)
- [ ] Set up custom CSS design system in `src/styles/main.css` from `website/style.css`
- [ ] Verify Python CLI works standalone after the move
- [ ] Update `.gitignore` for Rust (`target/`) and Node (`node_modules/`, `dist/`)

---

## Phase 1: Rust Core Library (audiosync-core)

**Goal**: Port all core logic to Rust with correctness validation against Python.

- [ ] Port `models.rs` — Clip, Track, SyncResult, SyncConfig structs with serde
- [ ] Port `grouping.rs` — Regex-based device name prefix grouping
- [ ] Port `metadata.rs` — ffprobe subprocess + JSON parsing
- [ ] Port `audio_io.rs` — File loading via symphonia, 8 kHz mono downsampling, cache management, ffmpeg for video, WAV export via hound
- [ ] Port `engine.rs` — FFT cross-correlation (`compute_delay`), drift detection (`measure_drift`), drift correction (`apply_drift_correction`), full analysis pipeline (`analyze`), sync stitching (`sync`)
- [ ] Port `project_io.rs` — serde_json, backward-compatible `.audiosync` format
- [ ] Port `timeline_export.rs` — FCPXML via quick-xml, EDL via string formatting
- [ ] Validation tests: generate fixtures from Python, verify Rust matches within tolerance

---

## Phase 2: Rust CLI (audiosync-cli)

**Goal**: Headless CLI binary for server/service/pipeline use.

- [ ] `audiosync analyze` — Run analysis, print JSON results
- [ ] `audiosync sync` — Analyze + export synced audio files
- [ ] `audiosync drift` — Standalone drift measurement/correction
- [ ] `audiosync info` — Show file metadata and grouping
- [ ] Flags: `--tracks`, `--output-dir`, `--format`, `--bit-depth`, `--reference`, `--max-offset`, `--json`
- [ ] Progress to stderr, results to stdout (pipe-friendly)
- [ ] Exit codes: 0 = success, 1 = error, 2 = low confidence warning
- [ ] Integration tests with audio fixtures

---

## Phase 3: Vue 3 Frontend Shell

**Goal**: Beautiful desktop UI matching the website's design language.

- [ ] Theme system (`src/styles/main.css`) — CSS custom properties from website/theme.py
- [ ] Background grid, glow orbs, glassmorphism cards, gradient text
- [ ] `MainLayout.vue` — App shell with Tauri menu, splitter
- [ ] `WorkflowBar.vue` — Three-step indicator with CSS animations
- [ ] `TrackPanel.vue` — Scrollable track list, + Add Track
- [ ] `TrackCard.vue` — Glassmorphism cards, file list, context menu, drag-and-drop
- [ ] `WaveformCanvas.vue` — Canvas 2D: time ruler, track lanes, waveform envelopes, zoom/pan, empty states, animated clip positioning

---

## Phase 4: Tauri Integration and Dialogs

**Goal**: Wire everything together, build all dialogs.

- [ ] Tauri commands: `import_files`, `analyze`, `sync_and_export`, `measure_drift`, `save_project`, `load_project`
- [ ] Progress streaming: `app.emit("sync-progress")` → Vue composable
- [ ] `ProcessingDialog.vue` — Progress bar, per-clip results, ETA, cancel
- [ ] `ExportDialog.vue` — Format/quality picker, drift correction toggle
- [ ] `DriftFixDialog.vue` — Standalone drift tool
- [ ] `AboutDialog.vue` — Version, credits, links
- [ ] File drag-and-drop via `tauri://drag-drop`
- [ ] Keyboard shortcuts via Tauri global shortcuts

---

## Phase 5: Cloud, Timeline Export, and Polish

**Goal**: Feature parity with the current Python app.

- [ ] Cloud client — reqwest, device-code OAuth, token via `tauri-plugin-store`
- [ ] `DeviceAuthDialog.vue` — User code display, polling animation
- [ ] `CloudProjectsDialog.vue` — List, save, load, delete
- [ ] Timeline export wired to UI with format picker
- [ ] Animation polish: workflow transitions, canvas clip animations, loading skeletons, toast notifications
- [ ] Responsive splitter layout

---

## Phase 6: Testing and Validation

**Goal**: Ensure correctness, reliability, and performance parity.

- [ ] Accuracy tests: Python vs Rust on identical recordings (offsets within 1 sample, confidence within 0.1, drift within 0.05 ppm)
- [ ] Rust unit tests per module
- [ ] CLI integration tests (end-to-end)
- [ ] Frontend component smoke tests
- [ ] Performance benchmarks: Python vs Rust analysis time
- [ ] Edge cases: empty tracks, single clips, huge files, mismatched sample rates, corrupt files, network failures

---

## Phase 7: Build Pipeline and Production Release

**Goal**: Ship cross-platform binaries with CI/CD.

- [ ] Tauri bundler: `.dmg` (macOS), `.msi` (Windows), `.deb`/`.AppImage` (Linux)
- [ ] GitHub Actions with `tauri-apps/tauri-action`
- [ ] CLI binary builds for all platforms
- [ ] App signing (macOS notarization, Windows code signing)
- [ ] Updated `README.md` — three usage modes, feature comparison, migration guide
- [ ] Website updates — new download links, CLI section
- [ ] Final QA on macOS, Windows, Linux

---

## What Gets Dropped

- `app/` directory (PyQt6 UI) — Replaced by Vue 3
- `main.py` (PyQt6 entry point) — Replaced by Tauri
- `build_app.sh`, `build_windows.bat`, `build_linux.sh` — Replaced by `tauri build`
- `opentimelineio` dependency — FCPXML exported directly
- `certifi` dependency — Rust reqwest handles TLS
- `PyQt6` dependency — No longer needed for main app

## What Stays

- `AudioSync.js` — Max for Live (untouched)
- `website/` — Marketing site (untouched)
- `icon.icns`, `icon.png` — Reused
- `.audiosync` project format — Same JSON schema, backward compatible
- Cloud API contract — Same endpoints, same auth flow
- Python core — Preserved in `python/` with CLI and documentation
