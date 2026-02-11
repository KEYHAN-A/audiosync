"""Project I/O — serialize / deserialize AudioSync projects to JSON.

Supports both local .audiosync files and cloud project blobs.
Excludes numpy arrays (samples, synced_audio) — those are reloaded from
source files on demand.
"""

from __future__ import annotations

import json
import logging
from typing import Optional

import numpy as np

from .models import Clip, SyncConfig, SyncResult, Track

logger = logging.getLogger("audiosync.project_io")

PROJECT_VERSION = "1.0"
FILE_EXTENSION = ".audiosync"


# ---------------------------------------------------------------------------
#  Serialize
# ---------------------------------------------------------------------------

def serialize_project(
    tracks: list[Track],
    sync_result: Optional[SyncResult],
    config: SyncConfig,
) -> dict:
    """
    Convert in-memory project state to a JSON-serializable dict.

    Excludes heavy data (numpy arrays) — only metadata and analysis
    results are stored. Audio is reloaded from source files on open.
    """
    return {
        "version": PROJECT_VERSION,
        "tracks": [_serialize_track(t) for t in tracks],
        "sync_result": _serialize_sync_result(sync_result) if sync_result else None,
        "config": _serialize_config(config),
    }


def _serialize_track(track: Track) -> dict:
    return {
        "name": track.name,
        "is_reference": track.is_reference,
        "clips": [_serialize_clip(c) for c in track.clips],
    }


def _serialize_clip(clip: Clip) -> dict:
    return {
        "file_path": clip.file_path,
        "name": clip.name,
        "duration_s": clip.duration_s,
        "original_sr": clip.original_sr,
        "original_channels": clip.original_channels,
        "is_video": clip.is_video,
        "creation_time": clip.creation_time,
        "timeline_offset_s": clip.timeline_offset_s,
        "timeline_offset_samples": clip.timeline_offset_samples,
        "confidence": clip.confidence,
        "analyzed": clip.analyzed,
    }


def _serialize_sync_result(result: SyncResult) -> dict:
    return {
        "reference_track_index": result.reference_track_index,
        "total_timeline_samples": result.total_timeline_samples,
        "total_timeline_s": result.total_timeline_s,
        "sample_rate": result.sample_rate,
        "clip_offsets": result.clip_offsets,
        "avg_confidence": result.avg_confidence,
        "warnings": result.warnings,
    }


def _serialize_config(config: SyncConfig) -> dict:
    return {
        "max_offset_s": config.max_offset_s,
        "export_format": config.export_format,
        "export_bit_depth": config.export_bit_depth,
        "export_sr": config.export_sr,
        "crossfade_ms": config.crossfade_ms,
    }


# ---------------------------------------------------------------------------
#  Deserialize
# ---------------------------------------------------------------------------

def deserialize_project(
    data: dict,
) -> tuple[list[Track], Optional[SyncResult], SyncConfig]:
    """
    Reconstruct project state from a serialized dict.

    Clips are created with empty samples arrays — audio must be
    reloaded from the source files separately.
    """
    version = data.get("version", "1.0")
    logger.info("Deserializing project version %s", version)

    tracks = [_deserialize_track(t) for t in data.get("tracks", [])]

    sync_data = data.get("sync_result")
    sync_result = _deserialize_sync_result(sync_data) if sync_data else None

    config_data = data.get("config", {})
    config = _deserialize_config(config_data)

    return tracks, sync_result, config


def _deserialize_track(data: dict) -> Track:
    clips = [_deserialize_clip(c) for c in data.get("clips", [])]
    return Track(
        name=data.get("name", "Untitled"),
        clips=clips,
        is_reference=data.get("is_reference", False),
    )


def _deserialize_clip(data: dict) -> Clip:
    return Clip(
        file_path=data.get("file_path", ""),
        name=data.get("name", "Unknown"),
        samples=np.array([], dtype=np.float32),  # empty — reload needed
        sample_rate=8000,
        original_sr=data.get("original_sr", 48000),
        original_channels=data.get("original_channels", 2),
        duration_s=data.get("duration_s", 0.0),
        is_video=data.get("is_video", False),
        creation_time=data.get("creation_time"),
        timeline_offset_samples=data.get("timeline_offset_samples", 0),
        timeline_offset_s=data.get("timeline_offset_s", 0.0),
        confidence=data.get("confidence", 0.0),
        analyzed=data.get("analyzed", False),
    )


def _deserialize_sync_result(data: dict) -> SyncResult:
    return SyncResult(
        reference_track_index=data.get("reference_track_index", 0),
        total_timeline_samples=data.get("total_timeline_samples", 0),
        total_timeline_s=data.get("total_timeline_s", 0.0),
        sample_rate=data.get("sample_rate", 8000),
        clip_offsets=data.get("clip_offsets", {}),
        avg_confidence=data.get("avg_confidence", 0.0),
        warnings=data.get("warnings", []),
    )


def _deserialize_config(data: dict) -> SyncConfig:
    return SyncConfig(
        max_offset_s=data.get("max_offset_s"),
        export_format=data.get("export_format", "wav"),
        export_bit_depth=data.get("export_bit_depth", 24),
        export_sr=data.get("export_sr"),
        crossfade_ms=data.get("crossfade_ms", 50.0),
    )


# ---------------------------------------------------------------------------
#  File I/O
# ---------------------------------------------------------------------------

def save_project(
    path: str,
    tracks: list[Track],
    sync_result: Optional[SyncResult],
    config: SyncConfig,
) -> None:
    """Save project to a .audiosync JSON file."""
    data = serialize_project(tracks, sync_result, config)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Project saved to %s", path)


def load_project(
    path: str,
) -> tuple[list[Track], Optional[SyncResult], SyncConfig]:
    """Load project from a .audiosync JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    logger.info("Project loaded from %s", path)
    return deserialize_project(data)
