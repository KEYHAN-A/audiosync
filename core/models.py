"""Data models for AudioSync core engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np


# ---------------------------------------------------------------------------
#  Clip — one audio/video file belonging to a Track
# ---------------------------------------------------------------------------

@dataclass
class Clip:
    """A single audio or video file imported into a track."""

    file_path: str
    name: str
    samples: np.ndarray                         # Mono, resampled to project SR
    sample_rate: int
    channels: int                               # Original channel count
    original_samples: np.ndarray                # Original multi-channel audio
    duration_s: float
    is_video: bool = False

    # Populated after analysis ------------------------------------------------
    timeline_offset_samples: int = 0            # Absolute position on timeline
    timeline_offset_s: float = 0.0
    confidence: float = 0.0                     # Cross-correlation confidence
    analyzed: bool = False

    @property
    def length_samples(self) -> int:
        return len(self.samples)

    @property
    def end_samples(self) -> int:
        return self.timeline_offset_samples + self.length_samples


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


# ---------------------------------------------------------------------------
#  SyncResult — output of the analysis phase
# ---------------------------------------------------------------------------

@dataclass
class SyncResult:
    """Results produced by the analysis engine."""

    reference_track_index: int
    total_timeline_samples: int                 # Length of the global timeline
    total_timeline_s: float
    sample_rate: int
    clip_offsets: dict[str, int] = field(default_factory=dict)
    # key = clip file_path, value = timeline offset in samples
    avg_confidence: float = 0.0
    warnings: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
#  SyncConfig — user-configurable parameters
# ---------------------------------------------------------------------------

@dataclass
class SyncConfig:
    """Configuration for the sync engine."""

    max_offset_s: Optional[float] = None        # None = no cap
    export_format: str = "wav"                   # "wav", "aiff", "flac"
    export_bit_depth: int = 24                   # 16, 24, or 32
    sample_rate: Optional[int] = None           # None = auto (highest among files)
    crossfade_ms: float = 50.0                  # Overlap crossfade duration

    @property
    def subtype(self) -> str:
        """Soundfile subtype string for the chosen bit depth."""
        mapping = {16: "PCM_16", 24: "PCM_24", 32: "FLOAT"}
        return mapping.get(self.export_bit_depth, "PCM_24")

    @property
    def format_str(self) -> str:
        """Soundfile format string."""
        mapping = {"wav": "WAV", "aiff": "AIFF", "flac": "FLAC"}
        return mapping.get(self.export_format.lower(), "WAV")
