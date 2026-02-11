"""Auto-grouping — group files by device name prefix."""

from __future__ import annotations

import re
from pathlib import Path


def group_files_by_device(paths: list[str]) -> dict[str, list[str]]:
    """
    Group file paths by their device/camera name prefix.

    Algorithm: strip trailing digits then trailing separators from the
    filename stem to get a "device key".

    Examples:
        GH010045.MP4, GH010046.MP4  →  {"GH": [...]}
        ZOOM0001.WAV, ZOOM0002.WAV  →  {"ZOOM": [...]}
        CamA_001.mp4, CamA_002.mp4  →  {"CamA": [...]}
        C0001.MP4                    →  {"C": [...]}
    """
    groups: dict[str, list[str]] = {}
    for path in paths:
        stem = Path(path).stem
        # Strip trailing digits, then trailing separators
        key = re.sub(r'[\d]+$', '', stem)
        key = key.rstrip('_- .')
        if not key:
            key = stem[:4] or "Import"
        groups.setdefault(key, []).append(path)

    # Sort files within each group by name
    for key in groups:
        groups[key].sort(key=lambda p: Path(p).name.lower())

    return groups
