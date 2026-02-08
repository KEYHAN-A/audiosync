"""
Timeline export — generate OTIO / FCPXML / EDL files from analysis results.

Converts AudioSync Pro's analysis data (clip offsets, durations, file paths,
track assignments) into timeline interchange formats that DaVinci Resolve,
Final Cut Pro, Premiere, and other NLEs can import.

Usage
-----
After ``analyze()`` completes, call ``export_timeline()`` with the tracks
and sync result.  No full sync/stitch step is required — only the offsets
and file paths are needed.

Supported output formats (auto-detected from file extension):
  .otio   — OpenTimelineIO native (recommended for DaVinci Resolve)
  .fcpxml — Final Cut Pro XML (also works in Resolve / Premiere)
  .edl    — Edit Decision List (legacy, single-track only)
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import opentimelineio as otio

from .models import Clip, SyncResult, Track

logger = logging.getLogger("audiosync.timeline_export")


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

def export_timeline(
    tracks: list[Track],
    sync_result: SyncResult,
    output_path: str,
    timeline_name: str = "AudioSync Pro",
    frame_rate: float = 24.0,
) -> str:
    """
    Export the analysed timeline to an NLE-compatible file.

    Parameters
    ----------
    tracks : list[Track]
        Tracks with analysed clips (``clip.analyzed`` must be True).
    sync_result : SyncResult
        The analysis result containing timeline metadata.
    output_path : str
        Destination file path.  Extension determines format:
        ``.otio``, ``.fcpxml``, or ``.edl``.
    timeline_name : str
        Name shown inside the NLE timeline.
    frame_rate : float
        Frame rate used for time representation (default 24 fps).

    Returns
    -------
    str
        The absolute path of the written file.

    Raises
    ------
    ValueError
        If no analysed clips are found or the format is unsupported.
    """
    analysed_tracks = [t for t in tracks if any(c.analyzed for c in t.clips)]
    if not analysed_tracks:
        raise ValueError("No analysed clips found. Run Analyze first.")

    timeline = _build_timeline(analysed_tracks, sync_result, timeline_name, frame_rate)

    # Write using OTIO — adapter is auto-selected from extension
    output_path = os.path.abspath(output_path)
    otio.adapters.write_to_file(timeline, output_path)

    logger.info("Timeline exported to %s", output_path)
    return output_path


def get_supported_formats() -> dict[str, str]:
    """Return a dict of {extension: description} for supported export formats."""
    return {
        ".otio": "OpenTimelineIO (recommended for DaVinci Resolve)",
        ".fcpxml": "Final Cut Pro XML (Resolve / Premiere / FCP)",
        ".edl": "Edit Decision List (legacy, single-track)",
    }


# ---------------------------------------------------------------------------
#  Internal — build the OTIO timeline
# ---------------------------------------------------------------------------

def _build_timeline(
    tracks: list[Track],
    sync_result: SyncResult,
    timeline_name: str,
    frame_rate: float,
) -> otio.schema.Timeline:
    """
    Construct an OTIO Timeline from AudioSync tracks.

    Each AudioSync Track becomes an OTIO Track.  Clips are sorted by their
    timeline offset, with Gap objects inserted for silence between them.
    """
    timeline = otio.schema.Timeline(name=timeline_name)
    timeline.global_start_time = otio.opentime.RationalTime(0, frame_rate)

    for track in tracks:
        analysed_clips = [c for c in track.clips if c.analyzed]
        if not analysed_clips:
            continue

        # Determine track kind from clip content
        has_video = any(c.is_video for c in analysed_clips)
        track_kind = (
            otio.schema.TrackKind.Video if has_video
            else otio.schema.TrackKind.Audio
        )

        otio_track = otio.schema.Track(
            name=track.name,
            kind=track_kind,
        )

        # Sort clips by timeline position
        sorted_clips = sorted(analysed_clips, key=lambda c: c.timeline_offset_s)

        # Build the track contents: [Gap, Clip, Gap, Clip, ...]
        cursor_s = 0.0  # Current position in seconds

        for clip in sorted_clips:
            offset_s = clip.timeline_offset_s
            duration_s = clip.duration_s

            # Insert a gap if there's silence before this clip
            gap_duration = offset_s - cursor_s
            if gap_duration > 0.001:  # > 1ms threshold
                gap = otio.schema.Gap(
                    source_range=otio.opentime.TimeRange(
                        start_time=otio.opentime.RationalTime(0, frame_rate),
                        duration=otio.opentime.RationalTime.from_seconds(
                            gap_duration, frame_rate
                        ),
                    ),
                )
                otio_track.append(gap)

            # Create the clip with a reference to the original media file
            media_ref = _make_media_reference(clip, frame_rate)

            otio_clip = otio.schema.Clip(
                name=clip.name,
                media_reference=media_ref,
                source_range=otio.opentime.TimeRange(
                    start_time=otio.opentime.RationalTime(0, frame_rate),
                    duration=otio.opentime.RationalTime.from_seconds(
                        duration_s, frame_rate
                    ),
                ),
            )

            # Store AudioSync metadata for reference
            otio_clip.metadata["audiosync"] = {
                "confidence": clip.confidence,
                "timeline_offset_s": offset_s,
                "original_sr": clip.original_sr,
                "original_channels": clip.original_channels,
                "is_video": clip.is_video,
                "is_reference": track.is_reference,
            }

            otio_track.append(otio_clip)
            cursor_s = offset_s + duration_s

        # Add a trailing gap to fill up to the total timeline length
        remaining = sync_result.total_timeline_s - cursor_s
        if remaining > 0.001:
            gap = otio.schema.Gap(
                source_range=otio.opentime.TimeRange(
                    start_time=otio.opentime.RationalTime(0, frame_rate),
                    duration=otio.opentime.RationalTime.from_seconds(
                        remaining, frame_rate
                    ),
                ),
            )
            otio_track.append(gap)

        timeline.tracks.append(otio_track)

    # Timeline-level metadata
    timeline.metadata["audiosync"] = {
        "total_timeline_s": sync_result.total_timeline_s,
        "avg_confidence": sync_result.avg_confidence,
        "analysis_sample_rate": sync_result.sample_rate,
        "reference_track_index": sync_result.reference_track_index,
    }

    return timeline


def _make_media_reference(
    clip: Clip,
    frame_rate: float,
) -> otio.schema.ExternalReference:
    """Create an OTIO ExternalReference pointing to the original media file."""
    file_path = os.path.abspath(clip.file_path)
    file_url = Path(file_path).as_uri()

    return otio.schema.ExternalReference(
        target_url=file_url,
        available_range=otio.opentime.TimeRange(
            start_time=otio.opentime.RationalTime(0, frame_rate),
            duration=otio.opentime.RationalTime.from_seconds(
                clip.duration_s, frame_rate
            ),
        ),
    )
