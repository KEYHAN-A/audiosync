"""Data models for AudioSync core engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np


# Analysis sample rate — low-res mono used for cross-correlation only.
# At 8 kHz precision is ~0.125 ms, more than enough for multi-device sync,
# while using ~36x less memory than 48 kHz.
ANALYSIS_SR = 8000


# ---------------------------------------------------------------------------
#  Clip — one audio/video file belonging to a Track
# ---------------------------------------------------------------------------

@dataclass
class Clip:
    """A single audio or video file imported into a track."""

    file_path: str
    name: str
    samples: np.ndarray                         # 8 kHz mono for analysis
    sample_rate: int                            # Always ANALYSIS_SR during analysis
    original_sr: int                            # Original file sample rate
    original_channels: int                      # Original channel count
    duration_s: float
    is_video: bool = False
    creation_time: Optional[float] = None       # Unix timestamp from file metadata

    # Populated after analysis ------------------------------------------------
    timeline_offset_samples: int = 0            # Position on timeline (analysis SR)
    timeline_offset_s: float = 0.0
    confidence: float = 0.0
    analyzed: bool = False

    @property
    def length_samples(self) -> int:
        return len(self.samples)

    @property
    def end_samples(self) -> int:
        return self.timeline_offset_samples + self.length_samples

    def timeline_offset_at_sr(self, target_sr: int) -> int:
        """Convert timeline offset from analysis SR to a target SR."""
        if self.sample_rate == target_sr:
            return self.timeline_offset_samples
        return int(round(self.timeline_offset_s * target_sr))

    def length_at_sr(self, target_sr: int) -> int:
        """Clip length in samples at a target SR."""
        return int(round(self.duration_s * target_sr))


# ---------------------------------------------------------------------------
#  Track — one recording device (camera, mic, Zoom, etc.)
# ---------------------------------------------------------------------------

@dataclass
class Track:
    """A device track containing one or more clips."""

    name: str
    clips: list[Clip] = field(default_factory=list)
    is_reference: bool = False

    # Populated after sync -----------------------------------------------------
    synced_audio: Optional[np.ndarray] = None   # Full-length stitched audio

    @property
    def total_duration_s(self) -> float:
        return sum(c.duration_s for c in self.clips)

    @property
    def clip_count(self) -> int:
        return len(self.clips)

    @property
    def total_samples(self) -> int:
        return sum(c.length_samples for c in self.clips)

    def sort_clips_by_time(self) -> None:
        """Sort clips by creation_time (then filename as fallback)."""
        self.clips.sort(key=lambda c: (c.creation_time or 0, c.name))


# ---------------------------------------------------------------------------
#  SyncResult — output of the analysis phase
# ---------------------------------------------------------------------------

@dataclass
class SyncResult:
    """Results produced by the analysis engine."""

    reference_track_index: int
    total_timeline_samples: int                 # At analysis SR
    total_timeline_s: float
    sample_rate: int                            # Analysis SR used
    clip_offsets: dict[str, int] = field(default_factory=dict)
    avg_confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
#  SyncConfig — user-configurable parameters
# ---------------------------------------------------------------------------

@dataclass
class SyncConfig:
    """Configuration for the sync engine."""

    max_offset_s: Optional[float] = None        # None = no cap
    export_format: str = "wav"                   # "wav", "aiff", "flac", "mp3"
    export_bit_depth: int = 24                   # 16, 24, or 32
    export_bitrate_kbps: int = 320               # MP3 bitrate (128, 192, 256, 320)
    export_sr: Optional[int] = None             # None = auto (highest among files)
    crossfade_ms: float = 50.0

    @property
    def is_lossy(self) -> bool:
        """True for lossy formats like MP3."""
        return self.export_format.lower() in ("mp3",)

    @property
    def subtype(self) -> str:
        """Soundfile subtype string for the chosen bit depth."""
        mapping = {16: "PCM_16", 24: "PCM_24", 32: "FLOAT"}
        return mapping.get(self.export_bit_depth, "PCM_24")

    @property
    def format_str(self) -> str:
        """Soundfile format string (for lossless formats only)."""
        mapping = {"wav": "WAV", "aiff": "AIFF", "flac": "FLAC"}
        return mapping.get(self.export_format.lower(), "WAV")


# ---------------------------------------------------------------------------
#  CancelledError
# ---------------------------------------------------------------------------

class CancelledError(Exception):
    """Raised when the user cancels a long-running operation."""
