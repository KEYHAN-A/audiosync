# AudioSync Pro

Multi-device audio/video synchronization tool. Syncs recordings from
multiple cameras, microphones, and recorders using FFT cross-correlation.

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

→ Exports 3 aligned WAV files, all the same length:

  Track 1: |=audio==silence==audio========================|
  Track 2: |==c1=c2==silence==c3=c4=...=silence==c12=====|
  Track 3: |===rec1=========rec2==========rec3==silence===|
```

---

## Requirements

- Python 3.10+
- ffmpeg (for video file support)

### Install ffmpeg

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

1. **Create tracks** — Click **+ Track** for each recording device.
   A loading screen shows progress while importing files.

2. **Import files** — Select a track, click **+ Files**, and add all
   audio/video files from that device. Drag-and-drop also works.
   Video audio is extracted automatically via ffmpeg. Supports WAV,
   AIFF, FLAC, MP3, MP4, MOV, MKV, AVI, WEBM, and more.

3. **Analyze** — Click **Analyze**. A processing screen shows live
   progress, per-clip results, elapsed time, and ETA. Analysis runs
   at 8 kHz for speed (~36x faster than full resolution). Cancel
   anytime with the Cancel button.

4. **Sync** — Click **Sync**. Each track's clips are stitched into
   a single continuous audio array at full resolution, with silence
   filling gaps.

5. **Export** — Click **Export** to save one synced audio file per
   track. Choose format (WAV/AIFF/FLAC) and bit depth (16/24/32).

6. **Reset** — Click **Reset** to clear analysis results and start over.

### Reference Track

The reference track is auto-detected (longest total audio duration).
To override, right-click a track and select **Set as Reference**.

### Keyboard Shortcuts

| Shortcut | Action          |
|----------|-----------------|
| Ctrl+T   | Add Track       |
| Ctrl+O   | Add Files       |
| Ctrl+E   | Export          |
| Ctrl+Z   | Reset           |
| Delete   | Remove Selected |
| Ctrl+Q   | Quit            |

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

> **Note:** ffmpeg must be installed on the system for video file
> support to work in the bundled application.

---

## Versioning

Version information is centralized in `version.py`. All modules,
build scripts, and the About dialog read from this single source.

```python
# version.py
__version__ = "2.1.0"
```

---

## Performance (v2.1)

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
   reference (user can override via right-click)
3. **Reference timeline** — Built using metadata timestamp gaps (not
   cross-correlation), correctly handling sequential same-device clips
4. **Pass 1 — Cross-correlation** — Every non-reference clip is
   cross-correlated against the full reference timeline
5. **Pass 2 — Enhanced timeline** — Low-confidence clips retried against
   an enhanced timeline that includes all successfully placed clips
6. **Stitching** — Clips placed at detected positions with silence gaps
7. **Export** — All tracks exported at same length, perfectly aligned

### Confidence Score

- **> 10**: Strong match, reliable alignment
- **3–10**: Moderate match, likely correct
- **< 3**: Weak match — may not overlap with reference

---

## Project Structure

```
├── main.py              Entry point
├── version.py           Centralized version info
├── requirements.txt     Python dependencies
├── build_app.sh         macOS .app build script
├── build_windows.bat    Windows .exe build script
├── build_linux.sh       Linux build script
├── icon.icns            macOS app icon
├── icon.png             App icon (PNG)
├── core/                Reusable DSP library (no GUI dependencies)
│   ├── models.py        Data models (Track, Clip, SyncResult, SyncConfig)
│   ├── audio_io.py      Audio/video loading, caching, export
│   ├── engine.py        Metadata-aware analysis, cross-correlation, stitcher
│   ├── metadata.py      ffprobe-based creation time extraction
│   └── grouping.py      Auto-grouping files by device name
├── app/                 PyQt6 desktop application
│   ├── main_window.py   Main window, toolbar, worker threads
│   ├── track_panel.py   Card-style track/file display
│   ├── waveform_view.py Timeline waveform display
│   ├── workflow_bar.py  Step indicator (Import→Analyze→Sync→Export)
│   ├── theme.py         Dark navy + cyan/purple theme
│   └── dialogs.py       Processing, import, export, about dialogs
├── website/             Landing page for web deployment
│   ├── index.html       Single-page landing
│   ├── style.css        Custom animations and glassmorphism
│   └── icon.png         App icon
└── AudioSync.js         Max for Live plugin for Ableton Live
```

---

## Website

The `website/` folder contains a static landing page ready for
deployment on any web server or subdomain. No build step required —
just copy the files and serve.

---

## Supported File Formats

### Audio
WAV, AIFF, FLAC, MP3, OGG, Opus

### Video (audio extracted via ffmpeg)
MP4, MOV, MKV, AVI, WEBM, MTS, M4V, MXF

---

## Dependencies

| Package    | Purpose                                  |
|------------|------------------------------------------|
| PyQt6      | Desktop GUI framework                    |
| numpy      | Array operations                         |
| scipy      | FFT-based cross-correlation              |
| soundfile  | Audio file I/O (WAV, AIFF, FLAC)        |
| ffmpeg     | Video audio extraction (system install)  |
