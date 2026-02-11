"""Metadata extraction — creation timestamps and file info via ffprobe."""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("audiosync.metadata")


def probe_creation_time(path: str) -> Optional[float]:
    """
    Extract creation_time as a Unix timestamp from an audio/video file.

    Fallback chain:
      1. format_tags.creation_time (most reliable for MP4/MOV)
      2. stream_tags.creation_time on the first audio stream
      3. File modification time (os.path.getmtime)
    """
    ffprobe = shutil.which("ffprobe")
    if ffprobe is None:
        return _file_mtime(path)

    try:
        cmd = [
            ffprobe, "-v", "quiet",
            "-print_format", "json",
            "-show_entries",
            "format_tags=creation_time:stream_tags=creation_time",
            path,
        ]
        result = subprocess.run(
            cmd, capture_output=True, timeout=10, text=True,
        )
        if result.returncode != 0:
            return _file_mtime(path)

        data = json.loads(result.stdout)

        # Try format-level creation_time first
        fmt_tags = data.get("format", {}).get("tags", {})
        ts = _parse_iso_timestamp(fmt_tags.get("creation_time"))
        if ts is not None:
            return ts

        # Try stream-level creation_time
        for stream in data.get("streams", []):
            tags = stream.get("tags", {})
            ts = _parse_iso_timestamp(tags.get("creation_time"))
            if ts is not None:
                return ts

    except Exception as exc:
        logger.debug("ffprobe metadata extraction failed for %s: %s", path, exc)

    return _file_mtime(path)


def _parse_iso_timestamp(value: Optional[str]) -> Optional[float]:
    """Parse an ISO 8601 timestamp string to Unix epoch seconds."""
    if not value:
        return None
    try:
        # Common formats from cameras:
        #   2024-01-15T20:32:09.000000Z
        #   2024-01-15T20:32:09Z
        #   2024-01-15 20:32:09
        value = value.strip()
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                dt = datetime.strptime(value, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.timestamp()
            except ValueError:
                continue
    except Exception:
        pass
    return None


def _file_mtime(path: str) -> Optional[float]:
    """Fallback: return the file's modification time."""
    try:
        return os.path.getmtime(path)
    except OSError:
        return None
