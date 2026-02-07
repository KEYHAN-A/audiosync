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

1. **Create tracks** — Click **+ Track** for each recording device
   (e.g. "Camera A", "Camera B", "Zoom H6").

2. **Import files** — Select a track, click **+ Files**, and add all
   audio/video files from that device. You can also drag-and-drop files
   directly onto a track. Supports WAV, AIFF, FLAC, MP3, MP4, MOV, MKV,
   AVI, WEBM, and more.

3. **Analyze** — Click **Analyze**. The engine uses FFT cross-correlation
   to detect where each clip sits on a global timeline. You'll see offsets
   and confidence scores for every clip.

4. **Sync** — Click **Sync**. Each track's clips are stitched into a
   single continuous audio array, with silence filling any gaps.

5. **Export** — Click **Export** to save one synced audio file per track.
   Choose output format (WAV/AIFF/FLAC) and bit depth (16/24/32-bit).

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

## How It Works

The core sync algorithm uses **FFT-based cross-correlation** to find
the precise time offset between recordings:

1. **Reference selection** — The track with the longest total audio
   becomes the reference (user can override).

2. **Reference timeline** — If the reference has multiple files, they
   are cross-correlated against each other to build a continuous
   reference array.

3. **Clip placement** — Every clip from every non-reference track is
   cross-correlated against the reference. The correlation peak reveals
   the exact sample offset where the clip belongs on the timeline.

4. **Stitching** — Each track's clips are placed at their detected
   positions in a silence array spanning the full timeline.

5. **Export** — All tracks are exported at the same length, perfectly
   aligned.

### Confidence Score

Each clip gets a confidence score (peak-to-mean ratio of the
cross-correlation). Higher is better:

- **> 10**: Strong match, reliable alignment
- **3–10**: Moderate match, likely correct
- **< 3**: Weak match — the clip may not overlap with the reference

---

## Project Structure

```
├── main.py              Entry point
├── requirements.txt     Python dependencies
├── core/                Reusable DSP library (no GUI dependencies)
│   ├── models.py        Data models (Track, Clip, SyncResult, SyncConfig)
│   ├── audio_io.py      Audio/video file loading and export
│   └── engine.py        Cross-correlation, timeline builder, stitcher
└── app/                 PyQt6 desktop application
    ├── main_window.py   Main window, toolbar, orchestration
    ├── track_panel.py   Track/file tree widget
    ├── waveform_view.py Timeline waveform display
    ├── theme.py         Dark pro-audio theme
    └── dialogs.py       Export and about dialogs
```

The `core/` library has zero GUI dependencies (only numpy, scipy,
soundfile). It can be reused in a CLI tool or ported to C++ for a
VST plugin.

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
