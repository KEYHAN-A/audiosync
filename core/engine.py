"""
AudioSync Engine — FFT cross-correlation, timeline builder, track stitcher.

Algorithm overview
------------------
1. REFERENCE SELECTION   — longest total audio (or user override)
2. BUILD REFERENCE TIMELINE — stitch multi-file reference into one array
3. PLACE CLIPS           — cross-correlate every clip against the reference
4. STITCH TRACKS         — combine clips per track into one continuous file
5. EXPORT                — handled by audio_io.export_track()
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
from scipy.signal import fftconvolve

from .models import Clip, Track, SyncConfig, SyncResult

logger = logging.getLogger("audiosync.engine")


# ---------------------------------------------------------------------------
#  Public API
# ---------------------------------------------------------------------------

def analyze(
    tracks: list[Track],
    config: SyncConfig,
    progress_callback=None,
) -> SyncResult:
    """
    Full analysis pipeline (steps 1-3).

    Parameters
    ----------
    tracks : list[Track]
        All tracks with clips loaded.
    config : SyncConfig
        Engine configuration.
    progress_callback : callable, optional
        Called with (current_step: int, total_steps: int, message: str).

    Returns
    -------
    SyncResult
    """
    if not tracks:
        raise ValueError("No tracks to analyze.")

    total_clips = sum(t.clip_count for t in tracks)
    if total_clips == 0:
        raise ValueError("No clips loaded in any track.")

    def _progress(step, total, msg):
        if progress_callback:
            progress_callback(step, total, msg)

    sr = config.sample_rate
    if sr is None:
        from .audio_io import detect_project_sample_rate
        sr = detect_project_sample_rate(tracks)
        config.sample_rate = sr

    total_steps = total_clips + 2  # +2 for ref selection and ref timeline

    # Step 1: Reference selection
    _progress(0, total_steps, "Selecting reference track...")
    ref_idx = _find_reference_index(tracks)
    ref_track = tracks[ref_idx]
    ref_track.is_reference = True
    logger.info("Reference track: '%s' (index %d)", ref_track.name, ref_idx)

    # Step 2: Build reference timeline
    _progress(1, total_steps, f"Building reference timeline from '{ref_track.name}'...")
    ref_audio = _build_reference_timeline(ref_track, config)
    logger.info("Reference timeline: %d samples (%.1f s)", len(ref_audio), len(ref_audio) / sr)

    # Step 3: Place every clip on the global timeline
    warnings: list[str] = []
    confidences: list[float] = []
    clip_offsets: dict[str, int] = {}
    step = 2

    for track in tracks:
        for clip in track.clips:
            step += 1
            _progress(step, total_steps, f"Placing '{clip.name}'...")

            if track.is_reference and clip.analyzed:
                # Already positioned during reference build
                clip_offsets[clip.file_path] = clip.timeline_offset_samples
                confidences.append(clip.confidence)
                continue

            if track.is_reference:
                # Reference clips already have positions from step 2
                clip_offsets[clip.file_path] = clip.timeline_offset_samples
                confidences.append(clip.confidence)
                continue

            delay, conf = compute_delay(
                ref_audio, clip.samples, sr, config.max_offset_s
            )

            clip.timeline_offset_samples = delay
            clip.timeline_offset_s = delay / sr
            clip.confidence = conf
            clip.analyzed = True

            clip_offsets[clip.file_path] = delay
            confidences.append(conf)

            if conf < 3.0:
                msg = f"Low confidence ({conf:.1f}) for '{clip.name}' — match may be unreliable"
                warnings.append(msg)
                logger.warning(msg)

    # Compute global timeline bounds
    min_offset = 0
    max_end = 0
    for track in tracks:
        for clip in track.clips:
            min_offset = min(min_offset, clip.timeline_offset_samples)
            max_end = max(max_end, clip.end_samples)

    # Shift everything so timeline starts at 0
    if min_offset < 0:
        shift = -min_offset
        for track in tracks:
            for clip in track.clips:
                clip.timeline_offset_samples += shift
                clip.timeline_offset_s = clip.timeline_offset_samples / sr
                clip_offsets[clip.file_path] = clip.timeline_offset_samples
        max_end += shift

    total_timeline_samples = max_end
    avg_conf = float(np.mean(confidences)) if confidences else 0.0

    result = SyncResult(
        reference_track_index=ref_idx,
        total_timeline_samples=total_timeline_samples,
        total_timeline_s=total_timeline_samples / sr,
        sample_rate=sr,
        clip_offsets=clip_offsets,
        avg_confidence=avg_conf,
        warnings=warnings,
    )

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
) -> None:
    """
    Apply alignment — stitch each track into a single continuous audio array.

    Modifies tracks in-place (sets track.synced_audio).
    """
    sr = result.sample_rate
    total_len = result.total_timeline_samples

    def _progress(step, total, msg):
        if progress_callback:
            progress_callback(step, total, msg)

    for i, track in enumerate(tracks):
        _progress(i, len(tracks), f"Stitching '{track.name}'...")
        track.synced_audio = _stitch_track(track, total_len, config)
        logger.info(
            "Stitched '%s': %d samples", track.name,
            len(track.synced_audio) if track.synced_audio is not None else 0,
        )


def auto_select_reference(tracks: list[Track]) -> int:
    """Return the index of the track with the longest total audio duration."""
    return _find_reference_index(tracks)


# ---------------------------------------------------------------------------
#  Cross-correlation
# ---------------------------------------------------------------------------

def compute_delay(
    reference: np.ndarray,
    target: np.ndarray,
    sr: int,
    max_offset_s: Optional[float] = None,
) -> tuple[int, float]:
    """
    Compute the time delay of *target* relative to *reference* using
    FFT-based cross-correlation.

    Returns
    -------
    delay_samples : int
        Positive = target starts *after* reference origin.
        Negative = target starts *before* reference origin.
    confidence : float
        Peak-to-mean ratio of the correlation. Higher = more reliable.
    """
    ref = reference.astype(np.float64)
    tgt = target.astype(np.float64)

    # Normalize
    ref_max = np.max(np.abs(ref))
    tgt_max = np.max(np.abs(tgt))
    if ref_max > 1e-10:
        ref = ref / ref_max
    if tgt_max > 1e-10:
        tgt = tgt / tgt_max

    # FFT cross-correlation: corr[k] = sum(ref[n] * tgt[n - k])
    correlation = fftconvolve(ref, tgt[::-1], mode="full")

    # The correlation output has length len(ref) + len(tgt) - 1
    # Index corresponding to zero delay = len(tgt) - 1

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

    # Confidence: peak / mean
    abs_corr = np.abs(correlation)
    mean_corr = np.mean(abs_corr)
    confidence = float(abs_corr[peak_idx] / (mean_corr + 1e-10))

    return delay_samples, confidence


# ---------------------------------------------------------------------------
#  Reference timeline builder
# ---------------------------------------------------------------------------

def _find_reference_index(tracks: list[Track]) -> int:
    """Pick the track with the longest total audio as reference."""
    # Check if user already set a reference
    for i, t in enumerate(tracks):
        if t.is_reference:
            return i

    best_idx = 0
    best_dur = 0.0
    for i, t in enumerate(tracks):
        dur = t.total_duration_s
        if dur > best_dur:
            best_dur = dur
            best_idx = i
    return best_idx


def _build_reference_timeline(track: Track, config: SyncConfig) -> np.ndarray:
    """
    Build a continuous reference audio array from a track's clips.

    If the track has one clip, return it directly.
    If multiple clips, cross-correlate clip[i] against clip[0] pairwise
    to find relative positions, then stitch with silence for gaps.
    """
    clips = track.clips
    if not clips:
        raise ValueError(f"Reference track '{track.name}' has no clips.")

    sr = config.sample_rate or 48000

    if len(clips) == 1:
        clips[0].timeline_offset_samples = 0
        clips[0].timeline_offset_s = 0.0
        clips[0].confidence = 100.0
        clips[0].analyzed = True
        return clips[0].samples.copy()

    # Multiple clips: cross-correlate each against clip[0]
    anchor = clips[0]
    anchor.timeline_offset_samples = 0
    anchor.timeline_offset_s = 0.0
    anchor.confidence = 100.0
    anchor.analyzed = True

    # First pass: find pairwise offsets against anchor
    # For long recordings, we correlate each clip against the anchor
    # to find where it sits relative to the anchor's start
    for i in range(1, len(clips)):
        delay, conf = compute_delay(anchor.samples, clips[i].samples, sr, config.max_offset_s)
        clips[i].timeline_offset_samples = delay
        clips[i].timeline_offset_s = delay / sr
        clips[i].confidence = conf
        clips[i].analyzed = True

    # Shift so minimum offset is 0
    min_off = min(c.timeline_offset_samples for c in clips)
    if min_off < 0:
        for c in clips:
            c.timeline_offset_samples -= min_off
            c.timeline_offset_s = c.timeline_offset_samples / sr

    # Build stitched array
    max_end = max(c.end_samples for c in clips)
    stitched = np.zeros(max_end, dtype=np.float64)

    for c in clips:
        start = c.timeline_offset_samples
        end = start + len(c.samples)
        segment = stitched[start:end]
        # Where there's silence, place audio directly; where overlap, average
        mask = np.abs(segment) < 1e-10
        stitched[start:end] = np.where(mask, c.samples[:len(segment)], (segment + c.samples[:len(segment)]) / 2)

    return stitched


# ---------------------------------------------------------------------------
#  Track stitcher
# ---------------------------------------------------------------------------

def _stitch_track(
    track: Track,
    total_length: int,
    config: SyncConfig,
) -> np.ndarray:
    """
    Stitch all clips in a track into one continuous audio array of
    *total_length* samples, placing each clip at its timeline offset.

    Uses the original multi-channel audio for quality, then mixes down
    to the maximum channel count found in the track.
    """
    if not track.clips:
        return np.zeros(total_length, dtype=np.float64)

    # Determine output channel count (max among clips in this track)
    max_ch = max(c.channels for c in track.clips)
    sr = config.sample_rate or 48000
    crossfade_samples = int((config.crossfade_ms / 1000.0) * sr)

    if max_ch == 1:
        output = np.zeros(total_length, dtype=np.float64)
    else:
        output = np.zeros((total_length, max_ch), dtype=np.float64)

    for clip in track.clips:
        start = clip.timeline_offset_samples
        if start < 0:
            start = 0

        # Use original samples for quality
        from .audio_io import resample_clip_original
        orig = resample_clip_original(clip, sr)

        # Ensure correct shape
        if max_ch == 1:
            if orig.ndim > 1:
                audio = orig.mean(axis=1)
            else:
                audio = orig
        else:
            if orig.ndim == 1:
                audio = np.column_stack([orig] * max_ch)
            elif orig.shape[1] < max_ch:
                # Pad channels
                pad = np.zeros((orig.shape[0], max_ch - orig.shape[1]), dtype=np.float64)
                audio = np.column_stack([orig, pad])
            else:
                audio = orig[:, :max_ch]

        # Place on timeline
        end = start + len(audio)
        if end > total_length:
            audio = audio[:total_length - start]
            end = total_length

        if start >= total_length:
            continue

        segment = output[start:end]

        # Simple overlap handling: mix where both have audio
        if max_ch == 1:
            has_audio = np.abs(segment) > 1e-10
            output[start:end] = np.where(has_audio, (segment + audio) / 2.0, audio)
        else:
            has_audio = np.any(np.abs(segment) > 1e-10, axis=1, keepdims=True)
            output[start:end] = np.where(has_audio, (segment + audio) / 2.0, audio)

    return output
