"""
AudioSync Engine — metadata-aware analysis with FFT cross-correlation.

Algorithm overview
------------------
1. Sort each track's clips by creation_time (from file metadata).
2. Auto-select reference track: the track whose clips span the widest
   time range (user can override via track.is_reference).
3. Build the reference timeline by placing the reference track's clips
   sequentially using metadata timestamp gaps (same-device clips CANNOT
   be cross-correlated — they are sequential, not overlapping).
4. Cross-correlate every non-reference clip against the reference
   timeline (Pass 1).
5. For clips with low confidence: build an enhanced timeline that
   includes high-confidence clips from ALL devices, then retry (Pass 2).
6. Metadata fallback for any remaining unmatched clips.
7. Normalize the timeline so the earliest offset is zero.

Performance notes
-----------------
- All analysis runs at ANALYSIS_SR (8 kHz mono).
- Every loop checks a cancel Event so the user can abort instantly.
- Export reads full-res audio on demand, one clip at a time.
"""

from __future__ import annotations

import logging
from threading import Event
from typing import Optional

import numpy as np
from scipy.signal import fftconvolve

from .models import (
    ANALYSIS_SR,
    CancelledError,
    Clip,
    SyncConfig,
    SyncResult,
    Track,
)

logger = logging.getLogger("audiosync.engine")

# Confidence threshold — clips below this are considered poorly matched
CONFIDENCE_THRESHOLD = 3.0


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

def analyze(
    tracks: list[Track],
    config: SyncConfig,
    progress_callback=None,
    cancel: Optional[Event] = None,
) -> SyncResult:
    """
    Full analysis pipeline — runs entirely at 8 kHz.

    Parameters
    ----------
    tracks : list[Track]
    config : SyncConfig
    progress_callback : callable(current, total, message)
    cancel : threading.Event, optional

    Returns
    -------
    SyncResult
    """
    if not tracks:
        raise ValueError("No tracks to analyze.")

    total_clips = sum(t.clip_count for t in tracks)
    if total_clips == 0:
        raise ValueError("No clips loaded in any track.")

    def _check():
        if cancel and cancel.is_set():
            raise CancelledError("Analysis cancelled")

    def _progress(step, total, msg):
        if progress_callback:
            progress_callback(step, total, msg)

    sr = ANALYSIS_SR
    # Steps: sort(1) + ref-build(1) + pass1(N) + pass2(up to N) + normalize(1)
    total_steps = total_clips + 4

    # ------------------------------------------------------------------
    # Phase 1: Sort clips by creation_time within each track
    # ------------------------------------------------------------------
    _progress(0, total_steps, "Sorting clips by creation time...")
    _check()

    for track in tracks:
        track.sort_clips_by_time()

    # ------------------------------------------------------------------
    # Phase 2: Select reference track
    # ------------------------------------------------------------------
    _progress(1, total_steps, "Selecting reference track...")
    _check()

    ref_idx = _select_reference_index(tracks)
    ref_track = tracks[ref_idx]
    ref_track.is_reference = True

    logger.info("Reference track: '%s' (index %d, %d clips)",
                ref_track.name, ref_idx, ref_track.clip_count)

    # ------------------------------------------------------------------
    # Phase 3: Build reference timeline from metadata gaps
    # ------------------------------------------------------------------
    _progress(2, total_steps, f"Building timeline from '{ref_track.name}' metadata...")
    _check()

    ref_audio = _build_reference_from_metadata(ref_track, sr)

    logger.info("Reference timeline: %.1f s (%d samples)",
                len(ref_audio) / sr, len(ref_audio))

    # ------------------------------------------------------------------
    # Phase 4: Cross-correlate non-reference clips (Pass 1)
    # ------------------------------------------------------------------
    warnings: list[str] = []
    confidences: list[float] = []
    clip_offsets: dict[str, int] = {}
    placed_clips: list[Clip] = []
    unplaced_clips: list[Clip] = []

    step = 2

    # Record reference clip offsets
    for clip in ref_track.clips:
        clip_offsets[clip.file_path] = clip.timeline_offset_samples
        confidences.append(clip.confidence)

    # Correlate all non-reference clips
    for track in tracks:
        if track is ref_track:
            continue
        for clip in track.clips:
            step += 1
            _progress(step, total_steps, f"Pass 1: correlating '{clip.name}'...")
            _check()

            delay, conf = compute_delay(
                ref_audio, clip.samples, sr, config.max_offset_s
            )

            clip.timeline_offset_samples = delay
            clip.timeline_offset_s = delay / sr
            clip.confidence = conf
            clip.analyzed = True

            clip_offsets[clip.file_path] = delay
            confidences.append(conf)

            if conf >= CONFIDENCE_THRESHOLD:
                placed_clips.append(clip)
            else:
                unplaced_clips.append(clip)
                msg = f"Low confidence ({conf:.1f}) for '{clip.name}'"
                warnings.append(msg)
                logger.warning(msg)

    _check()

    # ------------------------------------------------------------------
    # Phase 5: Enhanced timeline for unmatched clips (Pass 2)
    # ------------------------------------------------------------------
    if unplaced_clips:
        _progress(step + 1, total_steps, "Pass 2: building enhanced timeline...")
        _check()

        # Build enhanced timeline: reference + all high-confidence placed clips
        enhanced = _stitch_enhanced_timeline(ref_audio, placed_clips, sr)

        for clip in unplaced_clips:
            step += 1
            _progress(step, total_steps, f"Pass 2: retrying '{clip.name}'...")
            _check()

            delay, conf = compute_delay(
                enhanced, clip.samples, sr, config.max_offset_s
            )

            if conf > clip.confidence:
                clip.timeline_offset_samples = delay
                clip.timeline_offset_s = delay / sr
                clip.confidence = conf
                clip_offsets[clip.file_path] = delay

                if conf >= CONFIDENCE_THRESHOLD:
                    logger.info("Pass 2 improved '%s': confidence %.1f → %.1f",
                                clip.name, clip.confidence, conf)
                    # Remove from warnings if now good
                    warnings = [w for w in warnings if clip.name not in w]

        # Free enhanced timeline memory
        del enhanced

    _check()

    # ------------------------------------------------------------------
    # Phase 6: Metadata fallback for remaining unmatched
    # ------------------------------------------------------------------
    ref_origin = _get_track_time_origin(ref_track)
    for clip in unplaced_clips:
        if clip.confidence < CONFIDENCE_THRESHOLD and clip.creation_time and ref_origin:
            # Estimate position from metadata offset
            time_diff = clip.creation_time - ref_origin
            estimated_offset = int(time_diff * sr)
            if estimated_offset >= 0:
                clip.timeline_offset_samples = estimated_offset
                clip.timeline_offset_s = estimated_offset / sr
                clip_offsets[clip.file_path] = estimated_offset
                msg = f"'{clip.name}' placed via metadata fallback (confidence {clip.confidence:.1f})"
                warnings.append(msg)
                logger.warning(msg)

    # ------------------------------------------------------------------
    # Phase 7: Normalize timeline to start at 0
    # ------------------------------------------------------------------
    _progress(total_steps - 1, total_steps, "Normalizing timeline...")
    _check()

    min_offset = 0
    max_end = 0
    for track in tracks:
        for clip in track.clips:
            min_offset = min(min_offset, clip.timeline_offset_samples)
            max_end = max(max_end, clip.end_samples)

    if min_offset < 0:
        shift = -min_offset
        for track in tracks:
            for clip in track.clips:
                clip.timeline_offset_samples += shift
                clip.timeline_offset_s = clip.timeline_offset_samples / sr
                clip_offsets[clip.file_path] = clip.timeline_offset_samples
        max_end += shift

    avg_conf = float(np.mean(confidences)) if confidences else 0.0

    result = SyncResult(
        reference_track_index=ref_idx,
        total_timeline_samples=max_end,
        total_timeline_s=max_end / sr,
        sample_rate=sr,
        clip_offsets=clip_offsets,
        avg_confidence=avg_conf,
        warnings=warnings,
    )

    _progress(total_steps, total_steps, "Analysis complete.")

    logger.info(
        "Analysis complete: %d clips, timeline %.1f s, avg confidence %.1f",
        total_clips, result.total_timeline_s, avg_conf,
    )
    return result


def sync(
    tracks: list[Track],
    result: SyncResult,
    config: SyncConfig,
    progress_callback=None,
    cancel: Optional[Event] = None,
) -> None:
    """
    Stitch each track into a single continuous audio array at export SR.
    Re-reads original files at full resolution one clip at a time.
    """
    from .audio_io import read_clip_full_res, detect_project_sample_rate

    export_sr = config.export_sr
    if export_sr is None:
        export_sr = detect_project_sample_rate(tracks)
        config.export_sr = export_sr

    # Total timeline length at export SR
    total_len = int(round(result.total_timeline_s * export_sr))

    def _check():
        if cancel and cancel.is_set():
            raise CancelledError("Sync cancelled")

    def _progress(step, total, msg):
        if progress_callback:
            progress_callback(step, total, msg)

    total_steps = sum(t.clip_count for t in tracks)
    step = 0

    for track in tracks:
        _check()

        if not track.clips:
            track.synced_audio = np.zeros(total_len, dtype=np.float64)
            continue

        # Determine output channels
        max_ch = max(c.original_channels for c in track.clips)
        if max_ch == 1:
            output = np.zeros(total_len, dtype=np.float64)
        else:
            output = np.zeros((total_len, max_ch), dtype=np.float64)

        for clip in track.clips:
            step += 1
            _progress(step, total_steps, f"Stitching '{clip.name}'...")
            _check()

            # Re-read at full resolution
            audio = read_clip_full_res(clip, export_sr, cancel)

            # Convert offset from analysis SR to export SR
            start = clip.timeline_offset_at_sr(export_sr)
            if start < 0:
                start = 0

            # Shape audio for output
            if max_ch == 1:
                if audio.ndim > 1:
                    a = audio.mean(axis=1)
                else:
                    a = audio
            else:
                if audio.ndim == 1:
                    a = np.column_stack([audio] * max_ch)
                elif audio.shape[1] < max_ch:
                    pad = np.zeros((audio.shape[0], max_ch - audio.shape[1]), dtype=np.float64)
                    a = np.column_stack([audio, pad])
                else:
                    a = audio[:, :max_ch]

            end = start + len(a)
            if end > total_len:
                a = a[:total_len - start]
                end = total_len
            if start >= total_len:
                continue

            segment = output[start:end]
            if max_ch == 1:
                has_audio = np.abs(segment) > 1e-10
                output[start:end] = np.where(has_audio, (segment + a) / 2.0, a)
            else:
                has_audio = np.any(np.abs(segment) > 1e-10, axis=1, keepdims=True)
                output[start:end] = np.where(has_audio, (segment + a) / 2.0, a)

            # Free memory immediately
            del audio, a

        track.synced_audio = output

    logger.info("Sync complete: %d tracks stitched at %d Hz", len(tracks), export_sr)


def auto_select_reference(tracks: list[Track]) -> int:
    return _select_reference_index(tracks)


# ---------------------------------------------------------------------------
#  Cross-correlation (operates on 8 kHz data — fast and lightweight)
# ---------------------------------------------------------------------------

def compute_delay(
    reference: np.ndarray,
    target: np.ndarray,
    sr: int,
    max_offset_s: Optional[float] = None,
) -> tuple[int, float]:
    """
    FFT cross-correlation to find the delay of *target* relative to
    *reference*.  At 8 kHz this is extremely fast and memory-efficient.
    """
    ref = reference.astype(np.float32)
    tgt = target.astype(np.float32)

    # Normalize
    ref_max = np.max(np.abs(ref))
    tgt_max = np.max(np.abs(tgt))
    if ref_max > 1e-10:
        ref = ref / ref_max
    if tgt_max > 1e-10:
        tgt = tgt / tgt_max

    # FFT cross-correlation
    correlation = fftconvolve(ref, tgt[::-1], mode="full")

    if max_offset_s is not None:
        max_samples = int(max_offset_s * sr)
        center = len(tgt) - 1
        lo = max(0, center - max_samples)
        hi = min(len(correlation), center + max_samples + 1)
        search_region = correlation[lo:hi]
        peak_idx_local = int(np.argmax(np.abs(search_region)))
        peak_idx = peak_idx_local + lo
    else:
        peak_idx = int(np.argmax(np.abs(correlation)))

    delay_samples = peak_idx - (len(tgt) - 1)

    abs_corr = np.abs(correlation)
    mean_corr = float(np.mean(abs_corr))
    confidence = float(abs_corr[peak_idx] / (mean_corr + 1e-10))

    # Free correlation array immediately
    del correlation, abs_corr

    return delay_samples, confidence


# ---------------------------------------------------------------------------
#  Internal helpers
# ---------------------------------------------------------------------------

def _select_reference_index(tracks: list[Track]) -> int:
    """
    Select the reference track.

    Priority:
      1. User-set is_reference flag
      2. Track with the widest time coverage span (from metadata)
      3. Track with the longest total duration (fallback)
    """
    # Check for user override
    for i, t in enumerate(tracks):
        if t.is_reference:
            return i

    # Try metadata-based coverage span
    best_idx = 0
    best_span = 0.0
    for i, t in enumerate(tracks):
        span = _get_coverage_span(t)
        if span > best_span:
            best_span = span
            best_idx = i

    # If metadata was not available, fall back to total duration
    if best_span <= 0:
        best_dur = 0.0
        for i, t in enumerate(tracks):
            dur = t.total_duration_s
            if dur > best_dur:
                best_dur = dur
                best_idx = i

    return best_idx


def _get_coverage_span(track: Track) -> float:
    """
    Calculate the time span covered by a track's clips using metadata.
    Returns 0 if no metadata available.
    """
    times = [(c.creation_time, c.duration_s) for c in track.clips if c.creation_time]
    if not times:
        return 0.0
    earliest_start = min(t[0] for t in times)
    latest_end = max(t[0] + t[1] for t in times)
    return latest_end - earliest_start


def _get_track_time_origin(track: Track) -> Optional[float]:
    """Get the earliest creation_time in a track (the timeline origin)."""
    times = [c.creation_time for c in track.clips if c.creation_time]
    return min(times) if times else None


def _build_reference_from_metadata(track: Track, sr: int) -> np.ndarray:
    """
    Build reference timeline by placing clips sequentially using
    creation_time gaps from metadata.

    Same-device clips are sequential — they share NO overlapping audio.
    We CANNOT cross-correlate them. Instead, we use metadata timestamps
    to calculate exact gaps between clips.
    """
    clips = track.clips
    if not clips:
        raise ValueError(f"Reference track '{track.name}' has no clips.")

    # Single clip: trivial case
    if len(clips) == 1:
        clips[0].timeline_offset_samples = 0
        clips[0].timeline_offset_s = 0.0
        clips[0].confidence = 100.0
        clips[0].analyzed = True
        return clips[0].samples.copy()

    # Place clips using metadata gaps
    clips[0].timeline_offset_samples = 0
    clips[0].timeline_offset_s = 0.0
    clips[0].confidence = 100.0
    clips[0].analyzed = True

    for i in range(1, len(clips)):
        prev = clips[i - 1]
        curr = clips[i]

        if prev.creation_time and curr.creation_time:
            # Gap = next clip start - (previous clip start + previous clip duration)
            gap_s = curr.creation_time - (prev.creation_time + prev.duration_s)
            gap_s = max(gap_s, 0.0)  # no negative gaps (clock drift safety)
        else:
            # No metadata: assume small gap between sequential files
            gap_s = 0.5

        offset_samples = prev.timeline_offset_samples + prev.length_samples + int(gap_s * sr)
        curr.timeline_offset_samples = offset_samples
        curr.timeline_offset_s = offset_samples / sr
        curr.confidence = 100.0
        curr.analyzed = True

    # Stitch all clips into a single array with silence in gaps
    max_end = max(c.end_samples for c in clips)
    ref_audio = np.zeros(max_end, dtype=np.float32)

    for c in clips:
        start = c.timeline_offset_samples
        end = start + len(c.samples)
        seg_len = min(end, max_end) - start
        ref_audio[start:start + seg_len] = c.samples[:seg_len]

    return ref_audio


def _stitch_enhanced_timeline(
    ref_audio: np.ndarray,
    placed_clips: list[Clip],
    sr: int,
) -> np.ndarray:
    """
    Build an enhanced timeline by overlaying high-confidence clips
    from other devices on top of the reference timeline.

    This gives Pass 2 more audio to correlate against — useful when
    a clip only overlaps with a non-reference device that was placed
    in Pass 1.
    """
    if not placed_clips:
        return ref_audio

    # Find the maximum extent
    max_end = len(ref_audio)
    for clip in placed_clips:
        max_end = max(max_end, clip.end_samples)

    # Start with a copy of the reference
    enhanced = np.zeros(max_end, dtype=np.float32)
    enhanced[:len(ref_audio)] = ref_audio

    # Layer in placed clips
    for clip in placed_clips:
        start = clip.timeline_offset_samples
        if start < 0:
            continue
        end = start + len(clip.samples)
        seg_len = min(end, max_end) - start
        if seg_len <= 0:
            continue

        segment = enhanced[start:start + seg_len]
        clip_data = clip.samples[:seg_len]

        # Mix: where silence exists, use clip data; where audio exists, average
        mask = np.abs(segment) < 1e-10
        enhanced[start:start + seg_len] = np.where(mask, clip_data, (segment + clip_data) / 2)

    return enhanced
