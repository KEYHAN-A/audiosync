"""Main window — minimal layout with card-based tracks and timeline."""

from __future__ import annotations

import logging
import os
import traceback
from threading import Event
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.audio_io import (
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    cleanup_cache,
    clear_cache,
    detect_project_sample_rate,
    export_track,
    is_supported_file,
    load_clip,
)
from core.engine import analyze, sync
from core.grouping import group_files_by_device
from core.models import CancelledError, SyncConfig, SyncResult, Track
from core.timeline_export import export_timeline

from .dialogs import (
    AboutDialog,
    ExportDialog,
    ImportProgressDialog,
    ProcessingDialog,
    TimelineExportDialog,
)
from .theme import COLORS
from .track_card import TrackPanel
from .waveform_view import WaveformView
from .workflow_bar import Step, WorkflowBar

logger = logging.getLogger("audiosync.app")

_FILE_FILTER = (
    "Audio/Video Files ("
    + " ".join(f"*{ext}" for ext in sorted(AUDIO_EXTENSIONS | VIDEO_EXTENSIONS))
    + ");;All Files (*)"
)


# ---------------------------------------------------------------------------
#  Worker threads — all support cancellation via threading.Event
# ---------------------------------------------------------------------------

class _ImportWorker(QThread):
    """Load files in background thread."""

    progress = pyqtSignal(int, str)        # (index, filename)
    clip_loaded = pyqtSignal(object)       # Clip
    finished = pyqtSignal(list, list)      # (clips, errors)
    error = pyqtSignal(str)

    def __init__(self, paths: list[str], cancel: Event) -> None:
        super().__init__()
        self._paths = paths
        self._cancel = cancel

    def run(self) -> None:
        clips = []
        errors = []
        for i, p in enumerate(self._paths):
            if self._cancel.is_set():
                break
            self.progress.emit(i + 1, os.path.basename(p))
            try:
                clip = load_clip(p, cancel=self._cancel)
                clips.append(clip)
                self.clip_loaded.emit(clip)
            except CancelledError:
                break
            except Exception as exc:
                errors.append(f"{os.path.basename(p)}: {exc}")
        self.finished.emit(clips, errors)


class _AnalyzeWorker(QThread):
    """Run analysis in background thread."""

    progress = pyqtSignal(int, int, str)
    clip_result = pyqtSignal(str, float, float)  # (name, offset_s, confidence)
    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, tracks: list[Track], config: SyncConfig, cancel: Event) -> None:
        super().__init__()
        self._tracks = tracks
        self._config = config
        self._cancel = cancel

    def run(self) -> None:
        try:
            result = analyze(
                self._tracks,
                self._config,
                progress_callback=lambda c, t, m: self.progress.emit(c, t, m),
                cancel=self._cancel,
            )

            # Emit all clip results for the table
            for track in self._tracks:
                for clip in track.clips:
                    if clip.analyzed:
                        self.clip_result.emit(
                            clip.name, clip.timeline_offset_s, clip.confidence
                        )

            self.finished.emit(result)
        except CancelledError:
            self.error.emit("CANCELLED")
        except Exception as exc:
            self.error.emit(f"{exc}\n{traceback.format_exc()}")


class _SyncWorker(QThread):
    """Run sync/stitching in background thread."""

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(
        self, tracks: list[Track], result: SyncResult,
        config: SyncConfig, cancel: Event,
    ) -> None:
        super().__init__()
        self._tracks = tracks
        self._result = result
        self._config = config
        self._cancel = cancel

    def run(self) -> None:
        try:
            sync(
                self._tracks,
                self._result,
                self._config,
                progress_callback=lambda c, t, m: self.progress.emit(c, t, m),
                cancel=self._cancel,
            )
            self.finished.emit()
        except CancelledError:
            self.error.emit("CANCELLED")
        except Exception as exc:
            self.error.emit(f"{exc}\n{traceback.format_exc()}")


class _ExportWorker(QThread):
    """Export tracks in background thread with per-track progress."""

    progress = pyqtSignal(int, int, str)        # (current, total, track_name)
    finished = pyqtSignal(int, list)             # (exported_count, errors)

    def __init__(
        self,
        tracks: list[Track],
        output_dir: str,
        config: SyncConfig,
        cancel: Event,
    ) -> None:
        super().__init__()
        self._tracks = tracks
        self._output_dir = output_dir
        self._config = config
        self._cancel = cancel

    def run(self) -> None:
        exported = 0
        errors: list[str] = []
        exportable = [t for t in self._tracks if t.synced_audio is not None]
        total = len(exportable)

        for i, track in enumerate(exportable):
            if self._cancel.is_set():
                break
            self.progress.emit(i + 1, total, track.name)

            safe_name = "".join(
                c if c.isalnum() or c in " _-" else "_" for c in track.name
            )
            ext = self._config.export_format.lower()
            filename = f"{safe_name}_synced.{ext}"
            out_path = os.path.join(self._output_dir, filename)

            try:
                export_track(track, out_path, self._config)
                exported += 1
            except CancelledError:
                break
            except Exception as exc:
                errors.append(f"{track.name}: {exc}")

        self.finished.emit(exported, errors)


class _GroupedImportWorker(QThread):
    """Import files grouped by device into multiple tracks."""

    progress = pyqtSignal(int, str)        # (overall_index, filename)
    finished = pyqtSignal(dict, list)      # ({track_idx: [clips]}, errors)

    def __init__(self, groups: dict[int, list[str]], cancel: Event) -> None:
        super().__init__()
        self._groups = groups      # {track_idx: [paths]}
        self._cancel = cancel

    def run(self) -> None:
        results: dict[int, list] = {}
        errors: list[str] = []
        total = sum(len(paths) for paths in self._groups.values())
        idx = 0
        for track_idx, paths in self._groups.items():
            results[track_idx] = []
            for p in paths:
                if self._cancel.is_set():
                    self.finished.emit(results, errors)
                    return
                idx += 1
                self.progress.emit(idx, os.path.basename(p))
                try:
                    clip = load_clip(p, cancel=self._cancel)
                    results[track_idx].append(clip)
                except CancelledError:
                    self.finished.emit(results, errors)
                    return
                except Exception as exc:
                    errors.append(f"{os.path.basename(p)}: {exc}")
        self.finished.emit(results, errors)


# ---------------------------------------------------------------------------
#  MainWindow
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """AudioSync Pro main application window — minimal card-based layout."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AudioSync Pro")
        self.setMinimumSize(900, 560)
        self.resize(1080, 720)

        self._config = SyncConfig()
        self._sync_result: Optional[SyncResult] = None
        self._worker: Optional[QThread] = None
        self._cancel_event: Optional[Event] = None
        self._processing_dlg: Optional[ProcessingDialog] = None

        # Clean stale cache on startup
        cleanup_cache(max_age_hours=24)

        self._build_menubar()
        self._build_central()
        self._build_statusbar()
        self._update_button_states()

        self.setAcceptDrops(True)

    # =====================================================================
    #  UI construction
    # =====================================================================

    def _build_menubar(self) -> None:
        mb = self.menuBar()

        file_menu = mb.addMenu("&File")

        act = file_menu.addAction("Add &Track")
        act.setShortcut(QKeySequence("Ctrl+T"))
        act.triggered.connect(self._on_add_track)

        act = file_menu.addAction("Add &Files...")
        act.setShortcut(QKeySequence("Ctrl+O"))
        act.triggered.connect(self._on_add_files)

        file_menu.addSeparator()

        act = file_menu.addAction("&Analyze")
        act.setShortcut(QKeySequence("Ctrl+Shift+A"))
        act.triggered.connect(self._on_analyze)

        act = file_menu.addAction("&Sync")
        act.setShortcut(QKeySequence("Ctrl+Shift+S"))
        act.triggered.connect(self._on_sync)

        file_menu.addSeparator()

        act = file_menu.addAction("&Export...")
        act.setShortcut(QKeySequence("Ctrl+E"))
        act.triggered.connect(self._on_export)

        act = file_menu.addAction("Export &Timeline for NLE...")
        act.setShortcut(QKeySequence("Ctrl+Shift+T"))
        act.triggered.connect(self._on_export_timeline)

        file_menu.addSeparator()

        act = file_menu.addAction("Clear &Cache")
        act.triggered.connect(lambda: (clear_cache(), self._set_status("Cache cleared.")))

        file_menu.addSeparator()

        act = file_menu.addAction("&Quit")
        act.setShortcut(QKeySequence("Ctrl+Q"))
        act.triggered.connect(self.close)

        edit_menu = mb.addMenu("&Edit")

        act = edit_menu.addAction("&Reset")
        act.setShortcut(QKeySequence("Ctrl+Z"))
        act.triggered.connect(self._on_reset)

        act = edit_menu.addAction("R&emove Selected")
        act.setShortcut(QKeySequence("Delete"))
        act.triggered.connect(self._on_remove)

        help_menu = mb.addMenu("&Help")
        act = help_menu.addAction("&About AudioSync Pro")
        act.triggered.connect(lambda: AboutDialog(self).exec())

    def _build_central(self) -> None:
        # Main vertical layout: workflow bar + splitter(tracks | timeline)
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        # Workflow bar at top
        self._workflow_bar = WorkflowBar()
        self._workflow_bar.action_triggered.connect(self._on_workflow_action)
        central_layout.addWidget(self._workflow_bar)

        # Vertical splitter: track cards (top) | timeline (bottom)
        splitter = QSplitter(Qt.Orientation.Vertical)
        splitter.setHandleWidth(4)

        # Track panel
        self._track_panel = TrackPanel()
        self._track_panel.tracks_changed.connect(self._on_tracks_changed)
        self._track_panel.files_requested.connect(self._on_add_files_to_track)
        self._track_panel.files_dropped_on_empty.connect(self._on_files_dropped_empty)
        splitter.addWidget(self._track_panel)

        # Timeline / waveform view
        timeline_wrapper = QWidget()
        timeline_layout = QVBoxLayout(timeline_wrapper)
        timeline_layout.setContentsMargins(12, 4, 12, 4)
        timeline_layout.setSpacing(0)

        timeline_header = QLabel("TIMELINE")
        timeline_header.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 10px; font-weight: 600; "
            f"letter-spacing: 1.5px; padding: 6px 4px 2px;"
        )
        timeline_layout.addWidget(timeline_header)

        self._waveform = WaveformView()
        self._waveform.setMinimumHeight(100)
        timeline_layout.addWidget(self._waveform)

        splitter.addWidget(timeline_wrapper)
        splitter.setSizes([460, 200])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)

        central_layout.addWidget(splitter, stretch=1)
        self.setCentralWidget(central)

    def _build_statusbar(self) -> None:
        sb = self.statusBar()

        # Left: status message
        self._status_label = QLabel("Ready")
        sb.addWidget(self._status_label, stretch=1)

        # Center: summary counts
        self._summary_label = QLabel("")
        self._summary_label.setProperty("cssClass", "dim")
        self._summary_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sb.addWidget(self._summary_label, stretch=1)

        # Right: progress bar
        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedWidth(200)
        self._progress_bar.setFixedHeight(14)
        self._progress_bar.setVisible(False)
        sb.addPermanentWidget(self._progress_bar)

    # =====================================================================
    #  Actions
    # =====================================================================

    def _on_add_track(self) -> None:
        idx = self._track_panel.add_track()
        self._set_status(f"Created Track {idx + 1}")
        self._update_waveform()
        self._update_button_states()

    def _on_add_files(self) -> None:
        track_idx = self._track_panel.selected_track_index()
        if track_idx < 0:
            if not self._track_panel.tracks:
                track_idx = self._track_panel.add_track()
            else:
                self._set_status("Select a track first, or create a new one.")
                return
        self._on_add_files_to_track(track_idx)

    def _on_add_files_to_track(self, track_idx: int) -> None:
        pending_paths = getattr(self._track_panel, "_pending_drop_paths", None)
        if pending_paths:
            paths = pending_paths
            self._track_panel._pending_drop_paths = None
        else:
            paths, _ = QFileDialog.getOpenFileNames(
                self, "Add Audio/Video Files", "", _FILE_FILTER
            )
        if not paths:
            return

        self._start_import(track_idx, paths)

    def _start_import(self, track_idx: int, paths: list[str]) -> None:
        """Launch background import with progress dialog."""
        cancel = Event()
        self._cancel_event = cancel

        dlg = ImportProgressDialog(len(paths), self)

        worker = _ImportWorker(paths, cancel)
        worker.progress.connect(dlg.update_file)
        worker.finished.connect(
            lambda clips, errors: self._on_import_done(track_idx, clips, errors, dlg)
        )

        # Wire cancel button
        dlg._cancel_btn.clicked.disconnect()
        dlg._cancel_btn.clicked.connect(lambda: cancel.set())

        self._worker = worker
        worker.start()
        dlg.exec()

    def _on_import_done(
        self, track_idx: int, clips: list, errors: list, dlg: ImportProgressDialog,
    ) -> None:
        self._worker = None
        self._cancel_event = None
        dlg.accept()

        if clips:
            self._track_panel.add_clips_to_track(track_idx, clips)
            all_tracks = self._track_panel.tracks
            sr = detect_project_sample_rate(all_tracks)
            self._config.export_sr = sr

        if errors:
            msg = f"Loaded {len(clips)} file(s). {len(errors)} failed:\n"
            msg += "\n".join(errors[:5])
            self._set_status(msg)
            if len(errors) <= 5:
                QMessageBox.warning(self, "Import Warnings", msg)
        elif clips:
            track_name = self._track_panel.tracks[track_idx].name if track_idx < len(self._track_panel.tracks) else "track"
            self._set_status(f"Loaded {len(clips)} file(s) into '{track_name}'")
        else:
            self._set_status("Import cancelled.")

        self._update_waveform()
        self._update_button_states()

    def _on_remove(self) -> None:
        self._track_panel.remove_selected()
        self._update_waveform()
        self._update_button_states()

    # ----- Analyze ----------------------------------------------------------

    def _on_analyze(self) -> None:
        tracks = self._track_panel.tracks
        total_clips = sum(t.clip_count for t in tracks)
        if total_clips < 2:
            QMessageBox.information(
                self, "Not Enough Data",
                "Add at least 2 clips across your tracks to analyze.",
            )
            return

        cancel = Event()
        self._cancel_event = cancel

        dlg = ProcessingDialog("Analyzing", self)
        self._processing_dlg = dlg

        worker = _AnalyzeWorker(tracks, self._config, cancel)
        worker.progress.connect(dlg.update_progress)
        worker.clip_result.connect(dlg.add_clip_result)
        worker.finished.connect(lambda r: self._on_analyze_done(r, dlg))
        worker.error.connect(lambda e: self._on_worker_error(e, dlg))

        dlg._cancel_btn.clicked.disconnect()
        dlg._cancel_btn.clicked.connect(lambda: (
            cancel.set(),
            dlg._cancel_btn.setEnabled(False),
            dlg._cancel_btn.setText("Cancelling..."),
        ))

        self._worker = worker
        self._set_busy(True, "Analyzing...")
        worker.start()
        dlg.exec()

    def _on_analyze_done(self, result: SyncResult, dlg: ProcessingDialog) -> None:
        self._worker = None
        self._cancel_event = None

        self._sync_result = result
        self._track_panel.refresh()
        self._update_waveform(analyzed=True)
        self._set_busy(False)

        n_clips = sum(t.clip_count for t in self._track_panel.tracks)
        warnings_str = f"  ({len(result.warnings)} warnings)" if result.warnings else ""
        msg = (
            f"Analyzed {n_clips} clips — timeline {result.total_timeline_s:.1f}s, "
            f"avg confidence {result.avg_confidence:.1f}{warnings_str}"
        )
        self._set_status(msg)
        dlg.finish(f"Analysis complete — {n_clips} clips placed")
        self._update_button_states()

    # ----- Sync -------------------------------------------------------------

    def _on_sync(self) -> None:
        if self._sync_result is None:
            QMessageBox.information(
                self, "Analyze First",
                "Run Analyze before Sync to detect clip positions.",
            )
            return

        cancel = Event()
        self._cancel_event = cancel

        dlg = ProcessingDialog("Syncing", self)
        self._processing_dlg = dlg

        worker = _SyncWorker(
            self._track_panel.tracks, self._sync_result, self._config, cancel,
        )
        worker.progress.connect(dlg.update_progress)
        worker.finished.connect(lambda: self._on_sync_done(dlg))
        worker.error.connect(lambda e: self._on_worker_error(e, dlg))

        dlg._cancel_btn.clicked.disconnect()
        dlg._cancel_btn.clicked.connect(lambda: (
            cancel.set(),
            dlg._cancel_btn.setEnabled(False),
            dlg._cancel_btn.setText("Cancelling..."),
        ))

        self._worker = worker
        self._set_busy(True, "Syncing...")
        worker.start()
        dlg.exec()

    def _on_sync_done(self, dlg: ProcessingDialog) -> None:
        self._worker = None
        self._cancel_event = None

        self._set_busy(False)
        n_tracks = len(self._track_panel.tracks)
        self._set_status(f"Synced {n_tracks} track(s) — ready to export.")
        dlg.finish(f"Sync complete — {n_tracks} tracks ready to export")
        self._update_button_states()

    # ----- Reset / Export ---------------------------------------------------

    def _on_reset(self) -> None:
        self._sync_result = None
        self._track_panel.reset_analysis()
        self._update_waveform()
        self._set_status("Reset — analysis and sync results cleared.")
        self._update_button_states()

    def _on_export(self) -> None:
        tracks = self._track_panel.tracks
        has_synced = any(t.synced_audio is not None for t in tracks)
        if not has_synced:
            QMessageBox.information(
                self, "Sync First",
                "Run Analyze and Sync before exporting.",
            )
            return

        dlg = ExportDialog(self._config, len(tracks), self)
        if dlg.exec() != ExportDialog.DialogCode.Accepted:
            return

        output_dir = dlg.output_dir
        config = dlg.config
        os.makedirs(output_dir, exist_ok=True)

        cancel = Event()
        self._cancel_event = cancel

        proc_dlg = ProcessingDialog("Exporting", self)
        self._processing_dlg = proc_dlg

        worker = _ExportWorker(tracks, output_dir, config, cancel)
        worker.progress.connect(proc_dlg.update_progress)
        worker.finished.connect(
            lambda exported, errors: self._on_export_done(exported, errors, output_dir, proc_dlg)
        )

        proc_dlg._cancel_btn.clicked.disconnect()
        proc_dlg._cancel_btn.clicked.connect(lambda: (
            cancel.set(),
            proc_dlg._cancel_btn.setEnabled(False),
            proc_dlg._cancel_btn.setText("Cancelling..."),
        ))

        self._worker = worker
        self._set_busy(True, "Exporting...")
        worker.start()
        proc_dlg.exec()

    def _on_export_done(
        self, exported: int, errors: list, output_dir: str, dlg: ProcessingDialog,
    ) -> None:
        self._worker = None
        self._cancel_event = None
        self._set_busy(False)

        if errors:
            msg = f"Exported {exported}. Errors:\n" + "\n".join(errors)
            self._set_status(msg)
            dlg.finish(f"Exported {exported} tracks with {len(errors)} error(s)")
            QMessageBox.warning(self, "Export Warnings", msg)
        elif exported > 0:
            self._set_status(f"Exported {exported} track(s) to {output_dir}")
            dlg.finish(f"Exported {exported} synced audio file(s)")
        else:
            self._set_status("Export cancelled.")
            dlg.finish("Export cancelled")

        self._update_button_states()

    # ----- Export Timeline for NLE -------------------------------------------

    def _on_export_timeline(self) -> None:
        """Export the analysed timeline as an OTIO/FCPXML/EDL file for NLEs."""
        if self._sync_result is None:
            QMessageBox.information(
                self, "Analyze First",
                "Run Analyze before exporting a timeline.\n\n"
                "The timeline export only needs analysis results — "
                "you do not need to run Sync first.",
            )
            return

        tracks = self._track_panel.tracks
        total_clips = sum(
            sum(1 for c in t.clips if c.analyzed) for t in tracks
        )

        dlg = TimelineExportDialog(
            track_count=len(tracks),
            clip_count=total_clips,
            timeline_s=self._sync_result.total_timeline_s,
            parent=self,
        )
        if dlg.exec() != TimelineExportDialog.DialogCode.Accepted:
            return

        try:
            out = export_timeline(
                tracks=tracks,
                sync_result=self._sync_result,
                output_path=dlg.output_path,
                timeline_name=dlg.timeline_name,
                frame_rate=dlg.frame_rate,
            )
            self._set_status(f"Timeline exported to {out}")
            QMessageBox.information(
                self, "Timeline Exported",
                f"Timeline exported successfully.\n\n"
                f"File: {out}\n\n"
                f"Open this file in DaVinci Resolve via:\n"
                f"File → Import → Timeline",
            )
        except Exception as exc:
            QMessageBox.critical(
                self, "Export Failed",
                f"Failed to export timeline:\n\n{exc}",
            )

    # ----- Workflow bar actions ----------------------------------------------

    def _on_workflow_action(self, step_value: int) -> None:
        if step_value == -1:
            self._on_reset()
            return

        step = Step(step_value)
        if step == Step.IMPORT:
            self._on_add_files()
        elif step == Step.ANALYZE:
            self._on_analyze()
        elif step == Step.SYNC:
            self._on_sync()
        elif step == Step.EXPORT:
            self._on_export()

    # =====================================================================
    #  Auto-grouping drop
    # =====================================================================

    def _on_files_dropped_empty(self, paths: list[str]) -> None:
        groups = group_files_by_device(paths)

        track_map: dict[int, list[str]] = {}
        for device_name, file_paths in groups.items():
            idx = self._track_panel.add_track(name=device_name)
            track_map[idx] = file_paths

        total_files = sum(len(p) for p in track_map.values())
        if total_files == 0:
            return

        cancel = Event()
        self._cancel_event = cancel

        dlg = ImportProgressDialog(total_files, self)

        worker = _GroupedImportWorker(track_map, cancel)
        worker.progress.connect(dlg.update_file)
        worker.finished.connect(
            lambda results, errors: self._on_grouped_import_done(results, errors, dlg)
        )

        dlg._cancel_btn.clicked.disconnect()
        dlg._cancel_btn.clicked.connect(lambda: cancel.set())

        self._worker = worker
        worker.start()
        dlg.exec()

    def _on_grouped_import_done(
        self, results: dict, errors: list, dlg: ImportProgressDialog,
    ) -> None:
        self._worker = None
        self._cancel_event = None
        dlg.accept()

        total_clips = 0
        for track_idx, clips in results.items():
            if clips:
                self._track_panel.add_clips_to_track(track_idx, clips)
                total_clips += len(clips)

        if total_clips > 0:
            all_tracks = self._track_panel.tracks
            sr = detect_project_sample_rate(all_tracks)
            self._config.export_sr = sr

        n_groups = len(results)
        if errors:
            msg = f"Imported {total_clips} files into {n_groups} tracks. {len(errors)} failed."
            self._set_status(msg)
            if len(errors) <= 5:
                QMessageBox.warning(self, "Import Warnings", msg + "\n" + "\n".join(errors[:5]))
        elif total_clips > 0:
            self._set_status(f"Auto-grouped {total_clips} files into {n_groups} tracks")
        else:
            self._set_status("Import cancelled.")

        self._update_waveform()
        self._update_button_states()

    # =====================================================================
    #  Worker helpers
    # =====================================================================

    def _on_worker_error(self, error_msg: str, dlg: Optional[ProcessingDialog] = None) -> None:
        self._set_busy(False)
        self._worker = None
        self._cancel_event = None

        if error_msg == "CANCELLED":
            self._set_status("Operation cancelled.")
            if dlg:
                dlg.accept()
            self._update_button_states()
            return

        self._set_status("Error — see details.")
        if dlg:
            dlg.accept()
        QMessageBox.critical(self, "Error", error_msg[:1000])
        self._update_button_states()

    # =====================================================================
    #  UI helpers
    # =====================================================================

    def _set_status(self, msg: str) -> None:
        self._status_label.setText(msg)

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._progress_bar.setVisible(busy)
        self._progress_bar.setValue(0)
        if message:
            self._status_label.setText(message)

    def _update_button_states(self) -> None:
        tracks = self._track_panel.tracks
        has_tracks = len(tracks) > 0
        total_clips = sum(t.clip_count for t in tracks)
        has_analysis = self._sync_result is not None
        has_sync = any(t.synced_audio is not None for t in tracks)
        busy = self._worker is not None

        # Workflow bar
        self._workflow_bar.update_state(total_clips, has_analysis, has_sync, busy)

        # Summary counts in status bar
        if has_tracks:
            total_dur = sum(t.total_duration_s for t in tracks)
            dur_str = _fmt_duration(total_dur)
            self._summary_label.setText(
                f"{len(tracks)} track{'s' if len(tracks) != 1 else ''}, "
                f"{total_clips} clip{'s' if total_clips != 1 else ''}, "
                f"{dur_str} total"
            )
        else:
            self._summary_label.setText("")

    def _update_waveform(self, analyzed: bool = False) -> None:
        tracks = self._track_panel.tracks
        sr = self._config.export_sr or 48000

        if self._sync_result:
            total = int(round(self._sync_result.total_timeline_s * sr))
            analyzed = True
        else:
            total = int(sum(t.total_duration_s * sr for t in tracks))

        self._waveform.set_data(tracks, sr, total, analyzed=analyzed)

    def _on_tracks_changed(self) -> None:
        if self._sync_result is not None:
            self._sync_result = None
            for track in self._track_panel.tracks:
                track.synced_audio = None
                for clip in track.clips:
                    clip.analyzed = False
        self._update_waveform()
        self._update_button_states()

    # =====================================================================
    #  Drag-and-drop (on the main window itself)
    # =====================================================================

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasUrls():
            return

        paths = [
            url.toLocalFile() for url in event.mimeData().urls()
            if url.toLocalFile() and is_supported_file(url.toLocalFile())
        ]
        if not paths:
            return

        event.acceptProposedAction()
        self._on_files_dropped_empty(paths)

    # =====================================================================
    #  Cleanup on close
    # =====================================================================

    def closeEvent(self, event) -> None:
        if self._cancel_event:
            self._cancel_event.set()
        if self._worker and self._worker.isRunning():
            self._worker.wait(3000)
        clear_cache()
        event.accept()


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _fmt_duration(seconds: float) -> str:
    if seconds <= 0:
        return "0:00"
    total_s = int(seconds)
    h = total_s // 3600
    m = (total_s % 3600) // 60
    s = total_s % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"
