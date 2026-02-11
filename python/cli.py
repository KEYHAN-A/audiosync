#!/usr/bin/env python3
"""
AudioSync Pro — Command-line interface.

Usage examples:
    # Analyze and sync files, auto-grouping by device name
    python cli.py sync CamA_001.mp4 CamA_002.mp4 Zoom_001.wav Zoom_002.wav -o ./output

    # Manually specify tracks
    python cli.py sync --track "Camera A" CamA_*.mp4 --track "Zoom" Zoom_*.wav -o ./output

    # Just analyze (no export)
    python cli.py analyze CamA_001.mp4 CamA_002.mp4 Zoom_001.wav --json

    # Measure drift between two files
    python cli.py drift --reference ref.wav --target target.wav

    # Show file info and auto-grouping
    python cli.py info *.mp4 *.wav
"""

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path
from threading import Event

# Add this directory to path so core/ imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from version import __version__, APP_NAME
from core.models import SyncConfig, Track
from core.audio_io import (
    load_clip,
    export_track,
    is_supported_file,
    detect_project_sample_rate,
)
from core.engine import analyze, sync, measure_drift, compute_delay
from core.grouping import group_files_by_device
from core.metadata import probe_creation_time


logger = logging.getLogger("audiosync.cli")


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )


def _progress_callback(current: int, total: int, message: str) -> None:
    """Print progress to stderr."""
    pct = int(current / total * 100) if total > 0 else 0
    print(f"\r  [{pct:3d}%] {message}", end="", flush=True, file=sys.stderr)
    if current >= total:
        print(file=sys.stderr)


def _load_tracks_auto(file_paths: list[str], cancel: Event) -> list[Track]:
    """Load files and auto-group into tracks by device name."""
    valid = [p for p in file_paths if is_supported_file(p)]
    if not valid:
        print("Error: No supported audio/video files found.", file=sys.stderr)
        sys.exit(1)

    groups = group_files_by_device(valid)
    tracks = []

    for device_name, paths in groups.items():
        track = Track(name=device_name)
        for path in paths:
            print(f"  Loading {Path(path).name}...", file=sys.stderr)
            clip = load_clip(path, cancel)
            track.clips.append(clip)
        tracks.append(track)

    return tracks


def _load_tracks_manual(
    track_specs: list[tuple[str, list[str]]],
    cancel: Event,
) -> list[Track]:
    """Load files into manually specified tracks."""
    tracks = []
    for name, paths in track_specs:
        track = Track(name=name)
        for path in paths:
            if not is_supported_file(path):
                print(f"  Warning: Skipping unsupported file: {path}", file=sys.stderr)
                continue
            print(f"  Loading {Path(path).name} → {name}...", file=sys.stderr)
            clip = load_clip(path, cancel)
            track.clips.append(clip)
        if track.clips:
            tracks.append(track)
    return tracks


def _format_result(tracks: list[Track], result) -> dict:
    """Format analysis result as a JSON-serializable dict."""
    track_info = []
    for i, track in enumerate(tracks):
        clips_info = []
        for clip in track.clips:
            clips_info.append({
                "name": clip.name,
                "file_path": clip.file_path,
                "duration_s": round(clip.duration_s, 3),
                "offset_s": round(clip.timeline_offset_s, 6),
                "confidence": round(clip.confidence, 2),
                "drift_ppm": round(clip.drift_ppm, 3),
                "drift_confidence": round(clip.drift_confidence, 3),
            })
        track_info.append({
            "name": track.name,
            "is_reference": track.is_reference,
            "clips": clips_info,
        })

    return {
        "version": __version__,
        "reference_track_index": result.reference_track_index,
        "total_timeline_s": round(result.total_timeline_s, 3),
        "avg_confidence": round(result.avg_confidence, 2),
        "drift_detected": result.drift_detected,
        "warnings": result.warnings,
        "tracks": track_info,
    }


# ---------------------------------------------------------------------------
#  Commands
# ---------------------------------------------------------------------------

def cmd_analyze(args: argparse.Namespace) -> None:
    """Run analysis only — no export."""
    cancel = Event()
    config = SyncConfig(
        max_offset_s=args.max_offset,
    )

    print(f"AudioSync Pro {__version__} — Analyze", file=sys.stderr)
    print(f"Loading {len(args.files)} file(s)...", file=sys.stderr)

    tracks = _load_tracks_auto(args.files, cancel)

    print(f"Analyzing {sum(t.clip_count for t in tracks)} clips across "
          f"{len(tracks)} tracks...", file=sys.stderr)

    t0 = time.time()
    result = analyze(tracks, config, progress_callback=_progress_callback, cancel=cancel)
    elapsed = time.time() - t0

    if args.json:
        output = _format_result(tracks, result)
        output["elapsed_s"] = round(elapsed, 2)
        print(json.dumps(output, indent=2))
    else:
        print(f"\nAnalysis complete in {elapsed:.1f}s", file=sys.stderr)
        print(f"  Timeline: {result.total_timeline_s:.1f}s", file=sys.stderr)
        print(f"  Avg confidence: {result.avg_confidence:.1f}", file=sys.stderr)
        print(f"  Drift detected: {result.drift_detected}", file=sys.stderr)

        for i, track in enumerate(tracks):
            ref = " [REF]" if track.is_reference else ""
            print(f"\n  Track {i + 1}: {track.name}{ref}", file=sys.stderr)
            for clip in track.clips:
                drift_str = f", drift {clip.drift_ppm:+.2f} ppm" if abs(clip.drift_ppm) > 0.01 else ""
                print(f"    {clip.name}: offset {clip.timeline_offset_s:.3f}s, "
                      f"confidence {clip.confidence:.1f}{drift_str}", file=sys.stderr)

        if result.warnings:
            print(f"\nWarnings:", file=sys.stderr)
            for w in result.warnings:
                print(f"  ⚠ {w}", file=sys.stderr)


def cmd_sync(args: argparse.Namespace) -> None:
    """Analyze and export synced audio files."""
    cancel = Event()
    config = SyncConfig(
        max_offset_s=args.max_offset,
        export_format=args.format,
        export_bit_depth=args.bit_depth,
        drift_correction=not args.no_drift_correction,
    )

    print(f"AudioSync Pro {__version__} — Sync & Export", file=sys.stderr)
    print(f"Loading {len(args.files)} file(s)...", file=sys.stderr)

    tracks = _load_tracks_auto(args.files, cancel)

    print(f"Analyzing {sum(t.clip_count for t in tracks)} clips across "
          f"{len(tracks)} tracks...", file=sys.stderr)

    t0 = time.time()
    result = analyze(tracks, config, progress_callback=_progress_callback, cancel=cancel)

    print(f"\nSyncing and exporting...", file=sys.stderr)
    sync(tracks, result, config, progress_callback=_progress_callback, cancel=cancel)

    # Export
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    ext = config.export_format.lower()
    exported = []
    for track in tracks:
        filename = f"{track.name}.{ext}"
        output_path = os.path.join(output_dir, filename)
        export_track(track, output_path, config)
        exported.append(output_path)
        print(f"  Exported: {output_path}", file=sys.stderr)

    elapsed = time.time() - t0

    if args.json:
        output = _format_result(tracks, result)
        output["elapsed_s"] = round(elapsed, 2)
        output["exported_files"] = exported
        print(json.dumps(output, indent=2))
    else:
        print(f"\nDone in {elapsed:.1f}s — {len(exported)} files exported to {output_dir}",
              file=sys.stderr)


def cmd_drift(args: argparse.Namespace) -> None:
    """Measure or correct clock drift between two files."""
    from core.models import ANALYSIS_SR

    cancel = Event()

    print(f"AudioSync Pro {__version__} — Drift Measurement", file=sys.stderr)

    print(f"  Loading reference: {args.reference}...", file=sys.stderr)
    ref_clip = load_clip(args.reference, cancel)
    print(f"  Loading target: {args.target}...", file=sys.stderr)
    tgt_clip = load_clip(args.target, cancel)

    # First, find the delay
    delay, conf = compute_delay(
        ref_clip.samples, tgt_clip.samples, ANALYSIS_SR, max_offset_s=None
    )
    tgt_clip.timeline_offset_samples = delay
    tgt_clip.timeline_offset_s = delay / ANALYSIS_SR
    tgt_clip.confidence = conf

    # Build a simple reference timeline
    ref_audio = ref_clip.samples.copy()

    # Measure drift
    drift_ppm, r_squared = measure_drift(ref_audio, tgt_clip, ANALYSIS_SR)

    if args.json:
        print(json.dumps({
            "reference": args.reference,
            "target": args.target,
            "offset_s": round(delay / ANALYSIS_SR, 6),
            "confidence": round(conf, 2),
            "drift_ppm": round(drift_ppm, 3),
            "drift_r_squared": round(r_squared, 4),
        }, indent=2))
    else:
        print(f"\n  Offset: {delay / ANALYSIS_SR:.6f}s ({delay} samples @ {ANALYSIS_SR} Hz)",
              file=sys.stderr)
        print(f"  Confidence: {conf:.1f}", file=sys.stderr)
        print(f"  Drift: {drift_ppm:+.3f} ppm (R² = {r_squared:.4f})", file=sys.stderr)

        if abs(drift_ppm) > 0.3 and r_squared > 0.5:
            print(f"  Status: Significant drift detected", file=sys.stderr)
        else:
            print(f"  Status: No significant drift", file=sys.stderr)


def cmd_info(args: argparse.Namespace) -> None:
    """Show file info and auto-grouping."""
    valid = [p for p in args.files if is_supported_file(p)]
    if not valid:
        print("No supported files found.", file=sys.stderr)
        sys.exit(1)

    groups = group_files_by_device(valid)

    if args.json:
        output = {"groups": {}}
        for name, paths in groups.items():
            files = []
            for p in paths:
                ct = probe_creation_time(p)
                files.append({
                    "path": os.path.abspath(p),
                    "name": Path(p).name,
                    "creation_time": ct,
                })
            output["groups"][name] = files
        print(json.dumps(output, indent=2))
    else:
        print(f"AudioSync Pro {__version__} — File Info", file=sys.stderr)
        print(f"Found {len(valid)} supported file(s) in {len(groups)} group(s):\n",
              file=sys.stderr)
        for name, paths in groups.items():
            print(f"  Track: {name} ({len(paths)} files)", file=sys.stderr)
            for p in paths:
                ct = probe_creation_time(p)
                ct_str = f" (created: {ct:.0f})" if ct else ""
                print(f"    {Path(p).name}{ct_str}", file=sys.stderr)


# ---------------------------------------------------------------------------
#  Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="audiosync",
        description=f"{APP_NAME} {__version__} — Multi-device audio/video synchronization CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # --- analyze ---
    p_analyze = subparsers.add_parser("analyze", help="Analyze clip positions (no export)")
    p_analyze.add_argument("files", nargs="+", help="Audio/video files to analyze")
    p_analyze.add_argument("--max-offset", type=float, default=None,
                           help="Maximum offset in seconds (default: no limit)")
    p_analyze.add_argument("--json", action="store_true",
                           help="Output results as JSON to stdout")
    p_analyze.add_argument("-v", "--verbose", action="store_true")

    # --- sync ---
    p_sync = subparsers.add_parser("sync", help="Analyze, sync, and export audio files")
    p_sync.add_argument("files", nargs="+", help="Audio/video files to sync")
    p_sync.add_argument("-o", "--output-dir", default="./audiosync_output",
                        help="Output directory (default: ./audiosync_output)")
    p_sync.add_argument("--format", choices=["wav", "aiff", "flac", "mp3"],
                        default="wav", help="Export format (default: wav)")
    p_sync.add_argument("--bit-depth", type=int, choices=[16, 24, 32],
                        default=24, help="Bit depth (default: 24)")
    p_sync.add_argument("--max-offset", type=float, default=None,
                        help="Maximum offset in seconds (default: no limit)")
    p_sync.add_argument("--no-drift-correction", action="store_true",
                        help="Disable automatic clock drift correction")
    p_sync.add_argument("--json", action="store_true",
                        help="Output results as JSON to stdout")
    p_sync.add_argument("-v", "--verbose", action="store_true")

    # --- drift ---
    p_drift = subparsers.add_parser("drift", help="Measure clock drift between two files")
    p_drift.add_argument("--reference", "-r", required=True,
                         help="Reference audio/video file")
    p_drift.add_argument("--target", "-t", required=True,
                         help="Target audio/video file to measure")
    p_drift.add_argument("--json", action="store_true",
                         help="Output results as JSON to stdout")
    p_drift.add_argument("-v", "--verbose", action="store_true")

    # --- info ---
    p_info = subparsers.add_parser("info", help="Show file info and auto-grouping")
    p_info.add_argument("files", nargs="+", help="Audio/video files to inspect")
    p_info.add_argument("--json", action="store_true",
                        help="Output as JSON to stdout")
    p_info.add_argument("-v", "--verbose", action="store_true")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    _setup_logging(getattr(args, "verbose", False))

    commands = {
        "analyze": cmd_analyze,
        "sync": cmd_sync,
        "drift": cmd_drift,
        "info": cmd_info,
    }

    try:
        commands[args.command](args)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        logger.error("Error: %s", exc, exc_info=True)
        print(f"\nError: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
