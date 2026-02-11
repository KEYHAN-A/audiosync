# AudioSync Pro — Python Version

The original Python implementation of AudioSync Pro. This is preserved as an alternative for users who prefer Python or need to integrate with Python workflows.

> **Note:** The primary AudioSync Pro app is now built with Rust + Tauri v2. This Python version provides the same core algorithm via a command-line interface.

## Requirements

- Python 3.10+
- FFmpeg (for video file support)

## Setup

```bash
cd python/
python3 -m venv .venv
source .venv/bin/activate    # macOS/Linux
# .venv\Scripts\activate     # Windows

pip install -r requirements.txt
```

## CLI Usage

```bash
# Analyze files (auto-groups by device name)
python cli.py analyze CamA_001.mp4 CamA_002.mp4 Zoom_001.wav Zoom_002.wav

# Analyze with JSON output
python cli.py analyze *.mp4 *.wav --json

# Sync and export aligned audio files
python cli.py sync CamA_*.mp4 Zoom_*.wav -o ./output --format wav --bit-depth 24

# Measure clock drift between two files
python cli.py drift --reference ref.wav --target target.wav

# Show file info and auto-grouping
python cli.py info *.mp4 *.wav
```

## GUI Usage (Legacy)

The PyQt6 desktop app is still available:

```bash
python main.py
```

## Commands

| Command | Description |
|---------|-------------|
| `analyze` | Run analysis, print results (no export) |
| `sync` | Analyze + export synced audio files |
| `drift` | Measure clock drift between two files |
| `info` | Show file metadata and auto-grouping |

## Common Options

| Flag | Description |
|------|-------------|
| `--json` | Output results as JSON to stdout |
| `--format` | Export format: wav, aiff, flac, mp3 |
| `--bit-depth` | Bit depth: 16, 24, 32 |
| `--max-offset` | Maximum offset in seconds |
| `-o, --output-dir` | Output directory for exports |
| `-v, --verbose` | Verbose logging |

## Dependencies

| Package | Purpose |
|---------|---------|
| PyQt6 | Desktop GUI (legacy) |
| numpy | Array operations |
| scipy | FFT cross-correlation, resampling |
| soundfile | Audio file I/O |
| opentimelineio | NLE timeline export |
| certifi | SSL certificates |
