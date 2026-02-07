"""Audio I/O — load audio/video files, export aligned tracks."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from math import gcd

from .models import Clip, Track, SyncConfig


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
#  ffmpeg helpers
# ---------------------------------------------------------------------------

def _find_ffmpeg() -> str:
    """Locate ffmpeg binary."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError(
            "ffmpeg not found in PATH. Install ffmpeg to load video files.\n"
            "  macOS:   brew install ffmpeg\n"
            "  Linux:   sudo apt install ffmpeg\n"
            "  Windows: https://ffmpeg.org/download.html"
        )
    return ffmpeg


def _extract_audio_from_video(video_path: str, output_wav: str) -> None:
    """Extract audio from video to WAV using ffmpeg (lossless PCM)."""
    ffmpeg = _find_ffmpeg()
    cmd = [
        ffmpeg, "-y",
        "-i", video_path,
        "-vn",                  # No video
        "-acodec", "pcm_s24le", # 24-bit PCM for quality
        "-ar", "48000",         # Standardize SR for initial extraction
        output_wav,
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=300,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace")
        raise RuntimeError(f"ffmpeg failed for {video_path}:\n{stderr[:500]}")


# ---------------------------------------------------------------------------
#  Loading
# ---------------------------------------------------------------------------

def load_clip(path: str, target_sr: Optional[int] = None) -> Clip:
    """
    Load an audio or video file as a Clip.

    Parameters
    ----------
    path : str
        Path to audio or video file.
    target_sr : int, optional
        If provided, resample to this sample rate.

    Returns
    -------
    Clip
    """
    path = os.path.abspath(path)
    name = Path(path).name
    is_video = is_video_file(path)

    if is_video:
        # Extract audio to a temporary WAV
        tmp_dir = tempfile.mkdtemp(prefix="audiosync_")
        tmp_wav = os.path.join(tmp_dir, "extracted.wav")
        try:
            _extract_audio_from_video(path, tmp_wav)
            data, sr = sf.read(tmp_wav, dtype="float64")
        finally:
            # Clean up temp files
            try:
                os.remove(tmp_wav)
                os.rmdir(tmp_dir)
            except OSError:
                pass
    else:
        data, sr = sf.read(path, dtype="float64")

    # Ensure 2D: (samples, channels)
    if data.ndim == 1:
        data = data[:, np.newaxis]

    channels = data.shape[1]
    original_samples = data.copy()

    # Mono mixdown for analysis
    mono = data.mean(axis=1)

    # Resample if needed
    if target_sr is not None and target_sr != sr:
        mono = _resample(mono, sr, target_sr)
        sr = target_sr

    duration_s = len(mono) / sr

    return Clip(
        file_path=path,
        name=name,
        samples=mono,
        sample_rate=sr,
        channels=channels,
        original_samples=original_samples,
        duration_s=duration_s,
        is_video=is_video,
    )


def _resample(data: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample audio using polyphase filtering (high quality)."""
    if orig_sr == target_sr:
        return data
    g = gcd(orig_sr, target_sr)
    up = target_sr // g
    down = orig_sr // g
    # Limit polyphase filter size for very large ratios
    max_factor = 256
    while up > max_factor or down > max_factor:
        up = (up + 1) // 2
        down = (down + 1) // 2
        if up == 0:
            up = 1
        if down == 0:
            down = 1
    return resample_poly(data, up, down).astype(np.float64)


def resample_clip_original(clip: Clip, target_sr: int) -> np.ndarray:
    """Resample a clip's original multi-channel audio to target SR."""
    if clip.sample_rate == target_sr:
        return clip.original_samples

    orig_sr = clip.sample_rate
    g = gcd(orig_sr, target_sr)
    up = target_sr // g
    down = orig_sr // g
    max_factor = 256
    while up > max_factor or down > max_factor:
        up = (up + 1) // 2
        down = (down + 1) // 2
        if up == 0:
            up = 1
        if down == 0:
            down = 1

    if clip.original_samples.ndim == 1:
        return resample_poly(clip.original_samples, up, down).astype(np.float64)

    # Resample each channel
    channels = []
    for ch in range(clip.original_samples.shape[1]):
        channels.append(resample_poly(clip.original_samples[:, ch], up, down))
    return np.column_stack(channels).astype(np.float64)


# ---------------------------------------------------------------------------
#  Exporting
# ---------------------------------------------------------------------------

def export_track(
    track: Track,
    output_path: str,
    config: SyncConfig,
) -> str:
    """
    Export a track's synced audio to disk.

    Returns the absolute path of the written file.
    """
    if track.synced_audio is None:
        raise ValueError(f"Track '{track.name}' has no synced audio — run sync first.")

    output_path = os.path.abspath(output_path)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    audio = track.synced_audio
    # Clip to [-1, 1] to prevent distortion
    audio = np.clip(audio, -1.0, 1.0)

    sf.write(
        output_path,
        audio,
        config.sample_rate or 48000,
        subtype=config.subtype,
        format=config.format_str,
    )
    return output_path


def detect_project_sample_rate(tracks: list[Track]) -> int:
    """Detect the highest sample rate across all clips."""
    max_sr = 44100  # Minimum default
    for track in tracks:
        for clip in track.clips:
            if clip.sample_rate > max_sr:
                max_sr = clip.sample_rate
    return max_sr
