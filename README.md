# AudioSync Pro

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![GitHub](https://img.shields.io/badge/GitHub-KEYHAN--A%2Faudiosync-181717?logo=github)](https://github.com/KEYHAN-A/audiosync)
[![Version](https://img.shields.io/badge/version-3.1.0-38bdf8)](https://github.com/KEYHAN-A/audiosync/releases)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-a78bfa)]()
[![Website](https://img.shields.io/badge/website-audiosync.pro-38bdf8)](https://audiosync.pro)
[![CI](https://github.com/KEYHAN-A/audiosync/actions/workflows/ci.yml/badge.svg)](https://github.com/KEYHAN-A/audiosync/actions/workflows/ci.yml)

Multi-device audio/video synchronization with FFT cross-correlation, automatic clock drift detection, and NLE timeline export. Built with **Rust** and **Tauri v2** for native performance.

**Free and open source.** [Website](https://audiosync.pro) | [Download](https://github.com/KEYHAN-A/audiosync/releases) | [Report Issue](https://github.com/KEYHAN-A/audiosync/issues)

---

## What It Does

You record a session with multiple devices — Camera A rolls continuously, Camera B takes short B-roll clips throughout, and a Zoom recorder captures audio in several segments. All devices were running at the same time but started and stopped independently.

AudioSync Pro finds exactly where each clip sits on a shared timeline using audio cross-correlation, then exports one perfectly synced audio file per device. Drop the exports into any DAW or video editor and they line up.

### Key Features

- **FFT cross-correlation** — Sample-accurate sync across devices
- **Clock drift detection** — Measures and corrects drift (ppm) between devices
- **Auto-grouping** — Files grouped by device name automatically
- **NLE timeline export** — FCPXML (Final Cut Pro / DaVinci Resolve) and EDL (Premiere / Avid)
- **Multiple formats** — WAV, AIFF, FLAC, MP3 (16/24/32-bit)
- **Video support** — Extract audio from MP4, MOV, MKV, AVI, etc. via ffmpeg
- **Cloud save/load** — Save projects to the cloud via Keyhan Studio account (optional)
- **Timeline sharing** — Share synced timelines via a public link with interactive viewer
- **Cross-platform** — macOS, Windows, Linux

---

## Three Ways to Use AudioSync Pro

### 1. Desktop App (Tauri v2 + Vue 3)

The full GUI experience with waveform visualization, drag-and-drop, and real-time progress.

```bash
# Build and run
npm install
cargo tauri dev
```

**Features:** Glassmorphism UI, Canvas waveform timeline, resizable panels, file drag-and-drop, native menus, keyboard shortcuts (Cmd+O/S/R/E/D), progress dialogs, drift measurement tool, project save/load.

### 2. Rust CLI

Headless command-line tool for servers, pipelines, and automation.

```bash
# Build the CLI
cargo build --release -p audiosync-cli

# Analyze files
./target/release/audiosync analyze CamA_001.mp4 CamA_002.mp4 Zoom_001.wav --json

# Sync and export
./target/release/audiosync sync *.mp4 *.wav -o ./output --format wav --bit-depth 24

# Measure clock drift between two files
./target/release/audiosync drift -r reference.wav -t target.wav

# Show file info and auto-grouping
./target/release/audiosync info *.mp4 *.wav
```

**Flags:** `--json` for pipe-friendly output, `--max-offset` to constrain search, `--no-drift-correction`, `--save` for project files, `--fcpxml` / `--edl` for timeline export.

### 3. Python CLI (Legacy)

The original Python implementation is preserved in the `python/` directory for users who prefer it.

```bash
cd python/
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Analyze and sync
python cli.py analyze CamA_001.mp4 CamA_002.mp4 Zoom_001.wav
python cli.py sync CamA_001.mp4 CamA_002.mp4 Zoom_001.wav -o ./output
```

See [`python/README.md`](python/README.md) for full documentation.

---

## Architecture

```
AudioSyncPro/
├── audiosync-core/       # Rust library — engine, models, audio I/O
│   └── src/
│       ├── models.rs         # Clip, Track, SyncConfig, SyncResult
│       ├── audio_io.rs       # Symphonia + ffmpeg loading, rubato resampling, hound export
│       ├── engine.rs         # FFT cross-correlation, drift detection, analysis pipeline
│       ├── grouping.rs       # Auto-group files by device name
│       ├── metadata.rs       # ffprobe creation timestamps
│       ├── project_io.rs     # JSON project save/load
│       ├── timeline_export.rs# FCPXML v1.11 + EDL (CMX 3600)
│       └── cloud.rs          # Cloud API client (future)
├── audiosync-cli/        # Rust CLI binary
├── src-tauri/            # Tauri v2 desktop app (Rust backend)
│   └── src/
│       ├── commands.rs       # IPC bridge (15 commands)
│       ├── menu.rs           # Native app menu
│       └── lib.rs            # App entry, plugins, state
├── src/                  # Vue 3 frontend
│   ├── composables/
│   │   ├── useAudioSync.js   # Central state + Tauri invoke wrappers
│   │   ├── useAuth.js        # Device code OAuth + JWT session management
│   │   ├── useCloud.js       # Cloud project CRUD + timeline sharing
│   │   └── useToast.js       # Toast notification system
│   ├── components/
│   │   ├── MainLayout.vue    # App shell, toolbar, shortcuts, drag-drop
│   │   ├── WorkflowBar.vue   # 3-step workflow indicator
│   │   ├── TrackPanel.vue    # Track list sidebar
│   │   ├── TrackCard.vue     # Per-track card with clip list
│   │   ├── WaveformCanvas.vue# Canvas 2D timeline with waveform peaks
│   │   ├── ResizeSplitter.vue# Draggable panel divider
│   │   ├── LoginDialog.vue   # Device code login flow
│   │   ├── CloudProjectsDialog.vue  # Cloud project list + save/load
│   │   ├── ShareDialog.vue   # Timeline sharing via link
│   │   ├── ProcessingDialog.vue
│   │   ├── ExportDialog.vue
│   │   ├── DriftFixDialog.vue
│   │   ├── AboutDialog.vue
│   │   └── ToastNotification.vue
│   └── styles/
│       ├── main.css          # Glassmorphism design system
│       └── animations.css    # Transitions and keyframes
├── python/               # Legacy Python implementation (preserved)
├── website/              # Marketing website
├── .github/workflows/    # CI + Release pipelines
├── Cargo.toml            # Rust workspace
└── package.json          # Node.js (Vue + Vite)
```

---

## Algorithm

The analysis engine operates in 8 phases at 8 kHz mono:

1. **Sort** clips by creation timestamp (ffprobe metadata)
2. **Select reference** track (widest time coverage or longest duration)
3. **Build reference timeline** from metadata gaps between clips
4. **Pass 1**: FFT cross-correlation of each non-reference clip against the reference
5. **Pass 2**: Enhanced timeline retry for low-confidence clips (stitches all placed clips)
6. **Metadata fallback** for clips that still can't be matched
7. **Normalize** timeline so the earliest offset is zero
8. **Drift detection** via windowed cross-correlation + linear regression

**Confidence metric:** peak / mean ratio of the correlation (>3.0 = good match).

**Drift measurement:** Windowed cross-correlation at 30s intervals with 15s stride, sub-sample parabolic interpolation, linear regression of offsets → drift in ppm.

---

## Development

### Prerequisites

- **Rust** (stable) — `curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh`
- **Node.js** 20+ — `brew install node` or [nodejs.org](https://nodejs.org)
- **ffmpeg** — `brew install ffmpeg` (required for video files)

### Build

```bash
# Install frontend dependencies
npm install

# Run tests
cargo test --workspace

# Development mode (hot-reload)
cargo tauri dev

# Production build
cargo tauri build

# CLI only (no GUI dependencies)
cargo build --release -p audiosync-cli
```

### Test

```bash
# All tests (51 total: 41 unit + 9 CLI integration + 1 doctest)
cargo test --workspace

# Core library only
cargo test -p audiosync-core

# CLI integration tests
cargo test -p audiosync-cli
```

---

## Feature Comparison

| Feature | Desktop App | Rust CLI | Python CLI |
|---------|:-----------:|:--------:|:----------:|
| FFT cross-correlation | Yes | Yes | Yes |
| Clock drift detection | Yes | Yes | Yes |
| Drift correction | Yes | Yes | Yes |
| Auto-grouping | Yes | Yes | Yes |
| WAV/AIFF/FLAC/MP3 export | Yes | Yes | Yes |
| FCPXML timeline export | Yes | Yes | No |
| EDL timeline export | Yes | Yes | No |
| Waveform visualization | Yes | -- | -- |
| Drag-and-drop | Yes | -- | -- |
| Project save/load | Yes | Yes | No |
| Cloud save/load | Yes | -- | -- |
| Timeline sharing | Yes | -- | -- |
| JSON output | -- | Yes | Yes |
| Headless/server use | -- | Yes | Yes |
| GUI | Tauri + Vue 3 | -- | PyQt6 (legacy) |

---

## Migration from v2.x (Python)

AudioSync Pro v3.0 is a ground-up rewrite in Rust. The algorithm is identical but the implementation is new.

**What changed in v3.0:**
- Python/PyQt6 → Rust/Tauri v2 + Vue 3
- `soundfile` + `scipy` → `symphonia` + `rustfft` + `rubato`
- `opentimelineio` → native FCPXML/EDL generation
- Single binary → Cargo workspace with 3 crates

**What's new in v3.1.0:**
- Cloud save/load via Keyhan Studio account (optional, app works fully offline)
- Timeline sharing via public link with interactive waveform viewer
- Fixed drag-and-drop for Tauri v2 native file handling
- Fixed intra-track clip overlap enforcement
- Fixed FCPXML gap elements for DaVinci Resolve compatibility

**What stays:**
- The Python implementation in `python/` with its own CLI
- The `AudioSync.js` Max for Live device
- The website
- GPL-3.0 license

**Breaking changes:**
- Project file format is v2 (JSON) — not compatible with v1
- CLI syntax changed: `python cli.py analyze` → `audiosync analyze`

---

## License

GPL-3.0 — see [LICENSE](LICENSE).

Created by [Keyhan](https://github.com/KEYHAN-A).
