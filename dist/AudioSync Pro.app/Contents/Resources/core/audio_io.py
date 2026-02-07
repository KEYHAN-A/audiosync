"""Audio I/O — load audio/video files, export aligned tracks.

Performance strategy
--------------------
- On import: extract a **8 kHz mono** analysis copy (tiny in memory).
- During analysis: only 8 kHz data lives in RAM.
- On export: re-read original files at full resolution, one clip at a time,
  and write directly into the output array.  Never hold the entire project
  in memory at full resolution.
"""

from __future__ import annotations

import atexit
import hashlib
import logging
import os
import shutil
import subprocess
import tempfile
import time
from math import gcd
from pathlib import Path
from threading import Event
from typing import Optional

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

from .metadata import probe_creation_time
from .models import ANALYSIS_SR, Clip, Track, SyncConfig, CancelledError

logger = logging.getLogger("audiosync.io")

# ---------------------------------------------------------------------------
#  File type detection
# ---------------------------------------------------------------------------

AUDIO_EXTENSIONS = {".wav", ".aiff", ".aif", ".flac", ".mp3", ".ogg", ".opus"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".mts", ".m4v", ".mxf"}


def is_audio_file(path: str) -> bool:
    return Path(path).suffix.lower() in AUDIO_EXTENSIONS


def is_video_file(path: str) -> bool:
    return Path(path).suffix.lower() in VIDEO_EXTENSIONS


def is_supported_file(path: str) -> bool:
    return is_audio_file(path) or is_video_file(path)


# ---------------------------------------------------------------------------
#  Cache directory management
# ---------------------------------------------------------------------------

_CACHE_DIR = os.path.join(tempfile.gettempdir(), "audiosync_cache")


def _ensure_cache_dir() -> str:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    return _CACHE_DIR


def cleanup_cache(max_age_hours: float = 24.0) -> None:
    """Remove stale cache files older than *max_age_hours*."""
    if not os.path.isdir(_CACHE_DIR):
        return
    cutoff = time.time() - max_age_hours * 3600
    removed = 0
    for name in os.listdir(_CACHE_DIR):
        path = os.path.join(_CACHE_DIR, name)
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
                removed += 1
        except OSError:
            pass
    if removed:
        logger.info("Cache cleanup: removed %d stale file(s)", removed)


def clear_cache() -> None:
    """Delete the entire cache directory."""
    if os.path.isdir(_CACHE_DIR):
        shutil.rmtree(_CACHE_DIR, ignore_errors=True)
        logger.info("Cache cleared: %s", _CACHE_DIR)


# Cleanup on normal exit
atexit.register(clear_cache)


def _cache_key(path: str) -> str:
    """Stable cache key based on path + mtime + size."""
    try:
        stat = os.stat(path)
        raw = f"{os.path.abspath(path)}|{stat.st_mtime}|{stat.st_size}"
    except OSError:
        raw = os.path.abspath(path)
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
#  ffmpeg helpers
# ---------------------------------------------------------------------------

def _find_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError(
            "ffmpeg not found in PATH. Install ffmpeg to load video files.\n"
            "  macOS:   brew install ffmpeg\n"
            "  Linux:   sudo apt install ffmpeg\n"
            "  Windows: https://ffmpeg.org/download.html"
        )
    return ffmpeg


def _extract_audio_from_video(
    video_path: str,
    output_wav: str,
    sample_rate: int = ANALYSIS_SR,
    cancel: Optional[Event] = None,
) -> None:
    """Extract audio from video to mono WAV at *sample_rate* using ffmpeg."""
    ffmpeg = _find_ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-vn",                          # No video
        "-ac", "1",                     # Mono
        "-ar", str(sample_rate),        # Target SR
        "-acodec", "pcm_s16le",         # 16-bit (small, fast)
        output_wav,
    ]
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    # Poll so we can cancel
    while proc.poll() is None:
        if cancel and cancel.is_set():
            proc.kill()
            proc.wait()
            # Clean up partial file
            try:
                os.remove(output_wav)
            except OSError:
                pass
            raise CancelledError("Import cancelled")
        time.sleep(0.1)

    if proc.returncode != 0:
        stderr = proc.stderr.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ffmpeg failed for {video_path}:\n{stderr[:500]}")


def _get_original_audio_info(path: str) -> tuple[int, int]:
    """Get (sample_rate, channels) from an audio file without loading it."""
    info = sf.info(path)
    return info.samplerate, info.channels


def _probe_video_audio_info(path: str) -> tuple[int, int]:
    """Get (sample_rate, channels) from a video file using ffprobe."""
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return 48000, 2  # Safe fallback
    try:
        cmd = [
            ffprobe, "-v", "quiet",
            "-select_streams", "a:0",
            "-show_entries", "stream=sample_rate,channels",
            "-of", "csv=p=0",
            path,
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=10, text=True)
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            sr = int(parts[0])
            ch = int(parts[1]) if len(parts) > 1 else 2
            return sr, ch
    except Exception:
        pass
    return 48000, 2


# ---------------------------------------------------------------------------
#  Loading — lightweight 8 kHz analysis copy only
# ---------------------------------------------------------------------------

def load_clip(
    path: str,
    cancel: Optional[Event] = None,
) -> Clip:
    """
    Load an audio or video file as a Clip with 8 kHz mono analysis samples.
    Original full-resolution audio is NOT loaded into memory.
    """
    path = os.path.abspath(path)
    name = Path(path).name
    is_video = is_video_file(path)

    if is_video:
        # Get original info
        orig_sr, orig_channels = _probe_video_audio_info(path)

        # Extract 8 kHz mono to cache
        cache_dir = _ensure_cache_dir()
        key = _cache_key(path)
        cached_wav = os.path.join(cache_dir, f"{key}_analysis.wav")

        if not os.path.exists(cached_wav):
            _extract_audio_from_video(path, cached_wav, ANALYSIS_SR, cancel)

        data, sr = sf.read(cached_wav, dtype="float32")
    else:
        # Audio file: get info first
        orig_sr, orig_channels = _get_original_audio_info(path)

        # Read and downsample to analysis SR
        data, sr = sf.read(path, dtype="float32")

    if cancel and cancel.is_set():
        raise CancelledError("Import cancelled")

    # Ensure mono
    if data.ndim > 1:
        data = data.mean(axis=1)

    # Resample to analysis SR if needed
    if sr != ANALYSIS_SR:
        data = _resample(data, sr, ANALYSIS_SR)

    duration_s = len(data) / ANALYSIS_SR

    # Extract creation timestamp for metadata-aware sync
    creation_time = probe_creation_time(path)

    return Clip(
        file_path=path,
        name=name,
        samples=data.astype(np.float32),
        sample_rate=ANALYSIS_SR,
        original_sr=orig_sr,
        original_channels=orig_channels,
        duration_s=duration_s,
        is_video=is_video,
        creation_time=creation_time,
    )


# ---------------------------------------------------------------------------
#  On-demand full-resolution reading (for export only)
# ---------------------------------------------------------------------------

def read_clip_full_res(
    clip: Clip,
    target_sr: int,
    cancel: Optional[Event] = None,
) -> np.ndarray:
    """
    Re-read a clip's original file at full resolution, resampled to
    *target_sr*.  Returns a multi-channel float64 array.
    Used only during export — never kept in memory during analysis.
    """
    if clip.is_video:
        # Extract full-quality audio from video
        cache_dir = _ensure_cache_dir()
        key = _cache_key(clip.file_path)
        cached_full = os.path.join(cache_dir, f"{key}_full.wav")

        if not os.path.exists(cached_full):
            _extract_audio_full_quality(clip.file_path, cached_full, target_sr, cancel)

        data, sr = sf.read(cached_full, dtype="float64")

        # Clean up immediately — we read it, no need to keep on disk
        try:
            os.remove(cached_full)
        except OSError:
            pass
    else:
        data, sr = sf.read(clip.file_path, dtype="float64")

    if cancel and cancel.is_set():
        raise CancelledError("Export cancelled")

    # Ensure 2D
    if data.ndim == 1:
        data = data[:, np.newaxis]

    # Resample to target SR if needed
    if sr != target_sr:
        resampled_channels = []
        for ch in range(data.shape[1]):
            resampled_channels.append(_resample(data[:, ch], sr, target_sr))
        data = np.column_stack(resampled_channels)

    return data


def _extract_audio_full_quality(
    video_path: str,
    output_wav: str,
    target_sr: int,
    cancel: Optional[Event] = None,
) -> None:
    """Extract full-quality audio from video for export."""
    ffmpeg = _find_ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-vn",
        "-ar", str(target_sr),
        "-acodec", "pcm_s24le",
        output_wav,
    ]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    while proc.poll() is None:
        if cancel and cancel.is_set():
            proc.kill()
            proc.wait()
            try:
                os.remove(output_wav)
            except OSError:
                pass
            raise CancelledError("Export cancelled")
        time.sleep(0.1)

    if proc.returncode != 0:
        stderr = proc.stderr.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"ffmpeg export failed for {video_path}:\n{stderr[:500]}")


# ---------------------------------------------------------------------------
#  Resampling
# ---------------------------------------------------------------------------

def _resample(data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample audio using polyphase filtering (high quality)."""
    if orig_sr == target_sr:
        return data
    g = gcd(orig_sr, target_sr)
    up = target_sr // g
    down = orig_sr // g
    # Limit polyphase filter size
    max_factor = 256
    while up > max_factor or down > max_factor:
        up = (up + 1) // 2
        down = (down + 1) // 2
        if up < 1:
            up = 1
        if down < 1:
            down = 1
    return resample_poly(data, up, down).astype(data.dtype)


# ---------------------------------------------------------------------------
#  Exporting
# ---------------------------------------------------------------------------

def export_track(
    track: Track,
    output_path: str,
    config: SyncConfig,
) -> str:
    """Export a track's synced audio to disk."""
    if track.synced_audio is None:
        raise ValueError(f"Track '{track.name}' has no synced audio — run sync first.")

    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    audio = np.clip(track.synced_audio, -1.0, 1.0)

    sf.write(
        output_path,
        audio,
        config.export_sr or 48000,
        subtype=config.subtype,
        format=config.format_str,
    )
    return output_path


def detect_project_sample_rate(tracks: list[Track]) -> int:
    """Detect the highest original sample rate across all clips."""
    max_sr = 44100
    for track in tracks:
        for clip in track.clips:
            if clip.original_sr > max_sr:
                max_sr = clip.original_sr
    return max_sr
