# AudioSync Pro

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![GitHub](https://img.shields.io/badge/GitHub-KEYHAN--A%2Faudiosync-181717?logo=github)](https://github.com/KEYHAN-A/audiosync)
[![Version](https://img.shields.io/badge/version-2.5.1-38bdf8)](https://github.com/KEYHAN-A/audiosync/releases)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Windows%20%7C%20Linux-a78bfa)]()
[![Website](https://img.shields.io/badge/website-audiosync.keyhan.info-38bdf8)](https://audiosync.keyhan.info)
[![GitHub Pages](https://img.shields.io/badge/GitHub%20Pages-keyhan--a.github.io%2Faudiosync-222?logo=github)](https://keyhan-a.github.io/audiosync/)

Multi-device audio/video synchronization tool with high-quality audio processing. Syncs recordings from multiple cameras, microphones, and recorders using FFT cross-correlation. Export synced audio files (WAV, AIFF, FLAC, MP3) or NLE timelines for DaVinci Resolve, Final Cut Pro, and Premiere. Optional cloud sync via Keyhan Studio account.

**Free and open source.** [Website](https://audiosync.keyhan.info) | [GitHub Pages](https://keyhan-a.github.io/audiosync/) | [Download](https://github.com/KEYHAN-A/audiosync/releases) | [Report Issue](https://github.com/KEYHAN-A/audiosync/issues)

---

## What It Does

You record a session with multiple devices — Camera A rolls continuously,
Camera B takes short B-roll clips throughout, and a Zoom recorder captures
audio in several segments. All devices were running at the same time but
started and stopped independently.

AudioSync Pro finds exactly where each clip sits on a shared timeline
using audio cross-correlation, then exports one perfectly synced audio
file per device. Drop the exports into any DAW or video editor and they
line up.

### Example

```
Track 1 "Camera A":  2 files  (full-length video)
Track 2 "Camera B": 12 files  (short B-roll clips)
Track 3 "Zoom H6":   3 files  (audio recordings)

-> Exports 3 aligned audio files (WAV/AIFF/FLAC/MP3), all the same length:

  Track 1: |=audio==silence==audio========================|
  Track 2: |==c1=c2==silence==c3=c4=...=silence==c12=====|
  Track 3: |===rec1=========rec2==========rec3==silence===|
```

---

## High-Quality Audio Processing

AudioSync Pro is designed for professional audio workflows where quality matters:

- **24-bit PCM / 32-bit float** — Full bit-depth preservation throughout the pipeline
- **Polyphase resampling** — SciPy-powered sample rate conversion with minimal artifacts
- **Lossless format support** — Native WAV, AIFF, and FLAC export
- **MP3 export** — Lossy export via FFmpeg with configurable bitrate (128–320 kbps)
- **Clock drift correction** — Automatic detection and compensation of sample clock differences between devices, keeping audio aligned for the entire recording duration. Also available as a standalone tool (Tools > Fix Drift) for correcting individual files
- **Sample-rate preservation** — Exports at your project's highest native sample rate
- **Analysis at 8 kHz** — Cross-correlation runs on downsampled copies; your original files are never modified

---

## Requirements

- Python 3.10+
- FFmpeg (for video file support)

### Install FFmpeg

```bash
# macOS
brew install ffmpeg

# Linux
sudo apt install ffmpeg

# Windows
# Download from https://ffmpeg.org/download.html
```

---

## Setup

```bash
# Clone the repository
git clone https://github.com/KEYHAN-A/audiosync.git
cd audiosync

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

# Install dependencies
pip install -r requirements.txt
```

---

## Usage

```bash
source .venv/bin/activate
python main.py
```

### Workflow

1. **Import** — Create tracks for each recording device (click **+ Add Track**
   or drag-and-drop files to auto-group by device). Add audio or video files to
   each track. Supports WAV, AIFF, FLAC, MP3, MP4, MOV, MKV, AVI, WEBM, and more.

2. **Analyze & Sync** — Click **Analyze & Sync**. FFT cross-correlation
   runs at 8 kHz for speed, placing every clip on a shared timeline. Clock
   drift between devices is automatically detected and measured. A processing
   screen shows live progress, per-clip results, elapsed time, and ETA.
   Cancel anytime. After analysis, all clips are synced and shown on the timeline.

3. **Export** — Two export options are available after analysis:
   - **Export Audio** — Save one synced audio file per track. Choose format
     (WAV / AIFF / FLAC / MP3) and quality (bit depth for lossless, bitrate
     for MP3). Full-resolution stitching runs automatically before export.
     Clock drift is corrected transparently during export (toggle in dialog).
   - **Export Timeline for NLE** (Ctrl+Shift+T) — Export an `.otio`, `.fcpxml`,
     or `.edl` file. Open it in DaVinci Resolve, Final Cut Pro, or Premiere
     with all clips pre-arranged on a multi-track timeline.

4. **Reset** — Click **Reset** to clear analysis results and start over.

### Reference Track

The reference track is auto-detected (longest total audio duration).
To override, click the menu on a track card and select **Set as Reference**.

### Keyboard Shortcuts

| Shortcut       | Action                   |
|----------------|--------------------------|
| Ctrl+T         | Add Track                |
| Ctrl+O         | Add Files                |
| Ctrl+E         | Export Audio             |
| Ctrl+Shift+T   | Export Timeline for NLE  |
| Ctrl+Shift+D   | Fix Drift (standalone)   |
| Ctrl+Z         | Reset                    |
| Delete         | Remove Selected          |
| Ctrl+Q         | Quit                     |

---

## Build

### macOS (.app)

```bash
pip install pyinstaller
./build_app.sh
# Output: dist/AudioSync Pro.app
```

### Windows (.exe)

```batch
pip install pyinstaller
build_windows.bat
# Output: dist\AudioSync Pro\AudioSync Pro.exe
```

### Linux (portable binary / AppImage)

```bash
pip install pyinstaller
./build_linux.sh
# Output: dist/AudioSync Pro
# Optional: AppImage if appimagetool is installed
```

> **Note:** FFmpeg must be installed on the system for video file
> support to work in the bundled application.

---

## Versioning

Version information is centralized in `version.py`. All modules,
build scripts, and the About dialog read from this single source.

```python
# version.py
__version__ = "2.5.1"
```

---

## Performance

- **Analysis at 8 kHz**: Cross-correlation runs on 8 kHz mono audio,
  using ~36x less memory and CPU than 48 kHz. Temporal precision is
  ~0.125ms — more than enough for multi-device sync.

- **Minimal memory**: Only lightweight 8 kHz analysis data lives in
  memory. Full-resolution audio is re-read on demand during export.

- **Background processing**: All heavy operations (import, analyze,
  sync) run in background threads with cancel support.

- **Smart caching**: Cross-platform cache directory with LRU eviction
  (2 GB limit), per-session tracking for multi-instance safety, and
  automatic stale file cleanup on startup.

---

## How It Works

1. **Metadata extraction** — Creation timestamps extracted via ffprobe
   for accurate chronological ordering
2. **Reference selection** — Track with widest time coverage becomes
   reference (user can override via context menu)
3. **Reference timeline** — Built using metadata timestamp gaps (not
   cross-correlation), correctly handling sequential same-device clips
4. **Pass 1 — Cross-correlation** — Every non-reference clip is
   cross-correlated against the full reference timeline
5. **Pass 2 — Enhanced timeline** — Low-confidence clips retried against
   an enhanced timeline that includes all successfully placed clips
6. **Drift detection** — Windowed cross-correlation measures clock drift
   rate (ppm) per clip via linear regression, with sub-sample precision
7. **Stitching** — Clips placed at detected positions with silence gaps;
   drift-corrected by resampling during full-resolution export
8. **Export** — All tracks exported at same length, perfectly aligned

### Confidence Score

- **> 10**: Strong match, reliable alignment
- **3-10**: Moderate match, likely correct
- **< 3**: Weak match — may not overlap with reference

---

## DaVinci Resolve / NLE Export

After running **Analyze & Sync**, you can export the timeline directly for
your video editor.

**File → Export Timeline for NLE** (Ctrl+Shift+T) opens a dialog where
you choose:

- **Format**: `.otio` (recommended), `.fcpxml`, or `.edl`
- **Frame rate**: 24, 25, 30, etc.
- **Timeline name**: appears inside the NLE

The exported file contains:
- One track per device with all clips positioned at their detected offsets
- References to your **original media files** (video and audio)
- Gaps (silence) between clips matching the analysed timeline

### Import in DaVinci Resolve

1. Open DaVinci Resolve
2. Go to **File → Import → Timeline**
3. Select the `.otio` file
4. Resolve will create a timeline with all tracks and clips pre-arranged
5. Relink media if prompted (Resolve auto-detects files by name)

Also works with Final Cut Pro (`.fcpxml`) and legacy EDL workflows.

---

## Cloud Sync (Optional)

AudioSync Pro optionally integrates with [Keyhan Studio](https://studio.keyhan.info)
for cloud-synced projects:

- **Sign in** via the Account menu with your Google account
- **Save** projects to the cloud — all tracks, clips, offsets, and analysis results
- **Load** projects from any device running AudioSync Pro
- **100% optional** — the app works fully offline with no account required

Create a free account at [studio.keyhan.info/register](https://studio.keyhan.info/register).

---

## Project Structure

```
audiosync/
├── main.py              Entry point
├── version.py           Centralized version info
├── requirements.txt     Python dependencies
├── build_app.sh         macOS .app build script
├── build_windows.bat    Windows .exe build script
├── build_linux.sh       Linux build script
├── icon.icns            macOS app icon
├── icon.png             App icon (PNG)
├── LICENSE              GPL v3 license
├── CHANGELOG.md         Release history
├── CONTRIBUTING.md      Contributor guide
├── core/                Reusable DSP library (no GUI dependencies)
│   ├── models.py        Data models (Track, Clip, SyncResult, SyncConfig)
│   ├── audio_io.py      Audio/video loading, caching, export
│   ├── engine.py        Metadata-aware analysis, cross-correlation, stitcher
│   ├── timeline_export.py  OTIO/FCPXML/EDL export for DaVinci Resolve / NLEs
│   ├── metadata.py      ffprobe-based creation time extraction
│   ├── cloud.py         Cloud API client (Keyhan Studio integration)
│   └── grouping.py      Auto-grouping files by device name
├── app/                 PyQt6 desktop application
│   ├── main_window.py   Main window layout and worker threads
│   ├── track_card.py    Card-based track/file display
│   ├── waveform_view.py Timeline waveform display
│   ├── workflow_bar.py  Step indicator (Import->Analyze & Sync->Export)
│   ├── theme.py         Dark navy + cyan/purple theme
│   └── dialogs.py       Processing, import, export, about, sign-in dialogs
├── website/             Landing page for web deployment
│   ├── index.html       Single-page landing
│   ├── style.css        Custom animations and glassmorphism
│   └── icon.png         App icon
└── .github/workflows/   CI/CD pipeline scaffolds
```

---

## Website

Live at **[audiosync.keyhan.info](https://audiosync.keyhan.info)**
Mirror at **[keyhan-a.github.io/audiosync](https://keyhan-a.github.io/audiosync/)**

The `website/` folder contains a static landing page that is
automatically deployed via GitHub Actions on every push to `main`.
No build step required.

- **Production** — Deployed to `audiosync.keyhan.info` via SSH + rsync (`deploy.yml`)
- **GitHub Pages** — Deployed to `keyhan-a.github.io/audiosync` via GitHub Pages (`pages.yml`)

---

## Supported File Formats

### Audio
WAV, AIFF, FLAC, MP3, OGG, Opus

### Video (audio extracted via FFmpeg)
MP4, MOV, MKV, AVI, WEBM, MTS, M4V, MXF

---

## Deploy

The website is **automatically deployed** via GitHub Actions whenever
changes are pushed to the `website/` folder on `main`:

- **Production server** — `deploy.yml` syncs files via SSH + rsync to `audiosync.keyhan.info`
- **GitHub Pages** — `pages.yml` deploys to `keyhan-a.github.io/audiosync`

Builds (macOS/Windows/Linux) are created automatically on version
tags and uploaded as [GitHub Releases](https://github.com/KEYHAN-A/audiosync/releases).

---

## Dependencies

| Package          | Purpose                                         |
|------------------|-------------------------------------------------|
| PyQt6            | Desktop GUI framework                           |
| numpy            | Array operations                                |
| scipy            | FFT-based cross-correlation, resampling         |
| soundfile        | Audio file I/O (WAV, AIFF, FLAC)               |
| opentimelineio   | NLE timeline export (OTIO, FCPXML, EDL)         |
| FFmpeg           | Video audio extraction (system install)         |

---

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

AudioSync Pro is licensed under the [GNU General Public License v3.0](LICENSE).

## Author

Made by [Keyhan](https://keyhan.info)
