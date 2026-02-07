"""Main window — toolbar, splitter layout, orchestrates all components."""

from __future__ import annotations

import logging
import os
import traceback
from typing import Optional

from PyQt6.QtCore import Qt, QThread, pyqtSignal, QSize
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from core.audio_io import (
    AUDIO_EXTENSIONS,
    VIDEO_EXTENSIONS,
    detect_project_sample_rate,
    export_track,
    is_supported_file,
    load_clip,
)
from core.engine import analyze, sync
from core.models import SyncConfig, SyncResult, Track

from .dialogs import AboutDialog, ExportDialog
from .theme import COLORS
from .track_panel import TrackPanel
from .waveform_view import WaveformView

logger = logging.getLogger("audiosync.app")

_FILE_FILTER = (
    "Audio/Video Files ("
    + " ".join(f"*{ext}" for ext in sorted(AUDIO_EXTENSIONS | VIDEO_EXTENSIONS))
    + ");;All Files (*)"
)


# ---------------------------------------------------------------------------
#  Worker thread for long-running operations
# ---------------------------------------------------------------------------

class _AnalyzeWorker(QThread):
    """Run analysis in a background thread."""

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal(object)  # SyncResult or Exception
    error = pyqtSignal(str)

    def __init__(self, tracks: list[Track], config: SyncConfig) -> None:
        super().__init__()
        self._tracks = tracks
        self._config = config

    def run(self) -> None:
        try:
            result = analyze(
                self._tracks,
                self._config,
                progress_callback=lambda cur, tot, msg: self.progress.emit(cur, tot, msg),
            )
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(f"{exc}\n{traceback.format_exc()}")


class _SyncWorker(QThread):
    """Run sync/stitching in a background thread."""

    progress = pyqtSignal(int, int, str)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, tracks: list[Track], result: SyncResult, config: SyncConfig) -> None:
        super().__init__()
        self._tracks = tracks
        self._result = result
        self._config = config

    def run(self) -> None:
        try:
            sync(
                self._tracks,
                self._result,
                self._config,
                progress_callback=lambda cur, tot, msg: self.progress.emit(cur, tot, msg),
            )
            self.finished.emit()
        except Exception as exc:
            self.error.emit(f"{exc}\n{traceback.format_exc()}")


# ---------------------------------------------------------------------------
#  MainWindow
# ---------------------------------------------------------------------------

class MainWindow(QMainWindow):
    """AudioSync Pro main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("AudioSync Pro")
        self.setMinimumSize(900, 560)
        self.resize(1100, 680)

        self._config = SyncConfig()
        self._sync_result: Optional[SyncResult] = None
        self._worker: Optional[QThread] = None

        self._build_menubar()
        self._build_toolbar()
        self._build_central()
        self._build_statusbar()
        self._update_button_states()

        self.setAcceptDrops(True)

    # =====================================================================
    #  UI construction
    # =====================================================================

    def _build_menubar(self) -> None:
        mb = self.menuBar()

        # File menu
        file_menu = mb.addMenu("&File")

        act_add_track = file_menu.addAction("Add &Track")
        act_add_track.setShortcut(QKeySequence("Ctrl+T"))
        act_add_track.triggered.connect(self._on_add_track)

        act_add_files = file_menu.addAction("Add &Files...")
        act_add_files.setShortcut(QKeySequence("Ctrl+O"))
        act_add_files.triggered.connect(self._on_add_files)

        file_menu.addSeparator()

        act_export = file_menu.addAction("&Export...")
        act_export.setShortcut(QKeySequence("Ctrl+E"))
        act_export.triggered.connect(self._on_export)

        file_menu.addSeparator()

        act_quit = file_menu.addAction("&Quit")
        act_quit.setShortcut(QKeySequence("Ctrl+Q"))
        act_quit.triggered.connect(self.close)

        # Edit menu
        edit_menu = mb.addMenu("&Edit")

        act_reset = edit_menu.addAction("&Reset")
        act_reset.setShortcut(QKeySequence("Ctrl+Z"))
        act_reset.triggered.connect(self._on_reset)

        act_remove = edit_menu.addAction("R&emove Selected")
        act_remove.setShortcut(QKeySequence("Delete"))
        act_remove.triggered.connect(self._on_remove)

        # Help menu
        help_menu = mb.addMenu("&Help")
        act_about = help_menu.addAction("&About AudioSync Pro")
        act_about.triggered.connect(lambda: AboutDialog(self).exec())

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main Toolbar")
        tb.setMovable(False)
        tb.setIconSize(QSize(20, 20))
        self.addToolBar(tb)

        # Track management
        self._btn_add_track = QPushButton("+ Track")
        self._btn_add_track.setToolTip("Create a new device track (Ctrl+T)")
        self._btn_add_track.clicked.connect(self._on_add_track)
        tb.addWidget(self._btn_add_track)

        self._btn_add_files = QPushButton("+ Files")
        self._btn_add_files.setToolTip("Add audio/video files to selected track (Ctrl+O)")
        self._btn_add_files.clicked.connect(self._on_add_files)
        tb.addWidget(self._btn_add_files)

        self._btn_remove = QPushButton("Remove")
        self._btn_remove.setToolTip("Remove selected track or file (Delete)")
        self._btn_remove.setProperty("cssClass", "danger")
        self._btn_remove.clicked.connect(self._on_remove)
        tb.addWidget(self._btn_remove)

        tb.addSeparator()

        # Action buttons
        self._btn_analyze = QPushButton("  Analyze  ")
        self._btn_analyze.setProperty("cssClass", "accent")
        self._btn_analyze.setToolTip("Detect time offsets using cross-correlation")
        self._btn_analyze.clicked.connect(self._on_analyze)
        tb.addWidget(self._btn_analyze)

        self._btn_sync = QPushButton("  Sync  ")
        self._btn_sync.setProperty("cssClass", "accent")
        self._btn_sync.setToolTip("Apply alignment and stitch tracks")
        self._btn_sync.clicked.connect(self._on_sync)
        tb.addWidget(self._btn_sync)

        self._btn_reset = QPushButton("  Reset  ")
        self._btn_reset.setProperty("cssClass", "danger")
        self._btn_reset.setToolTip("Clear analysis and sync results (Ctrl+Z)")
        self._btn_reset.clicked.connect(self._on_reset)
        tb.addWidget(self._btn_reset)

        tb.addSeparator()

        self._btn_export = QPushButton("  Export  ")
        self._btn_export.setToolTip("Export synced audio files (Ctrl+E)")
        self._btn_export.clicked.connect(self._on_export)
        tb.addWidget(self._btn_export)

    def _build_central(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: track panel
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(0)

        panel_header = QLabel("  TRACKS & FILES")
        panel_header.setProperty("cssClass", "heading")
        panel_header.setFixedHeight(28)
        left_layout.addWidget(panel_header)

        self._track_panel = TrackPanel()
        self._track_panel.tracks_changed.connect(self._on_tracks_changed)
        self._track_panel.files_requested.connect(self._on_add_files_to_track)
        left_layout.addWidget(self._track_panel)

        # Right: waveform view
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        waveform_header = QLabel("  TIMELINE")
        waveform_header.setProperty("cssClass", "heading")
        waveform_header.setFixedHeight(28)
        right_layout.addWidget(waveform_header)

        self._waveform = WaveformView()
        right_layout.addWidget(self._waveform)

        splitter.addWidget(left)
        splitter.addWidget(right)
        splitter.setSizes([360, 740])
        self.setCentralWidget(splitter)

    def _build_statusbar(self) -> None:
        sb = self.statusBar()
        self._status_label = QLabel("Ready")
        sb.addWidget(self._status_label, stretch=1)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedWidth(200)
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
        """Add files to the selected track (or create one first)."""
        track_idx = self._track_panel.selected_track_index()
        if track_idx < 0:
            if not self._track_panel.tracks:
                track_idx = self._track_panel.add_track()
            else:
                self._set_status("Select a track first, or create a new one.")
                return

        self._on_add_files_to_track(track_idx)

    def _on_add_files_to_track(self, track_idx: int) -> None:
        """Add files to a specific track index."""
        # Check for pending drag-and-drop paths
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

        self._load_files_to_track(track_idx, paths)

    def _load_files_to_track(self, track_idx: int, paths: list[str]) -> None:
        """Load files and add them to a track."""
        self._set_status(f"Loading {len(paths)} file(s)...")
        QApplication.processEvents()

        clips = []
        errors = []
        for p in paths:
            try:
                clip = load_clip(p, target_sr=self._config.sample_rate)
                clips.append(clip)
            except Exception as exc:
                errors.append(f"{os.path.basename(p)}: {exc}")
                logger.error("Failed to load %s: %s", p, exc)

        if clips:
            self._track_panel.add_clips_to_track(track_idx, clips)

            # Auto-detect sample rate from all tracks
            all_tracks = self._track_panel.tracks
            sr = detect_project_sample_rate(all_tracks)
            self._config.sample_rate = sr

        if errors:
            msg = f"Loaded {len(clips)} file(s). Failed to load {len(errors)}:\n"
            msg += "\n".join(errors[:5])
            if len(errors) > 5:
                msg += f"\n... and {len(errors) - 5} more"
            self._set_status(msg)
            QMessageBox.warning(self, "Import Warnings", msg)
        else:
            self._set_status(f"Loaded {len(clips)} file(s) into '{self._track_panel.tracks[track_idx].name}'")

        self._update_waveform()
        self._update_button_states()

    def _on_remove(self) -> None:
        self._track_panel.remove_selected()
        self._update_waveform()
        self._update_button_states()

    def _on_analyze(self) -> None:
        """Run cross-correlation analysis."""
        tracks = self._track_panel.tracks
        total_clips = sum(t.clip_count for t in tracks)
        if total_clips < 2:
            QMessageBox.information(
                self,
                "Not Enough Data",
                "Add at least 2 clips across your tracks to analyze.",
            )
            return

        self._set_busy(True, "Analyzing...")
        self._worker = _AnalyzeWorker(tracks, self._config)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_analyze_done)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    def _on_analyze_done(self, result: SyncResult) -> None:
        self._sync_result = result
        self._track_panel.refresh()
        self._update_waveform(analyzed=True)
        self._set_busy(False)

        n_clips = sum(t.clip_count for t in self._track_panel.tracks)
        warnings_str = f"  ({len(result.warnings)} warnings)" if result.warnings else ""
        self._set_status(
            f"Analyzed {n_clips} clips — timeline {result.total_timeline_s:.1f}s, "
            f"avg confidence {result.avg_confidence:.1f}{warnings_str}"
        )
        self._update_button_states()

    def _on_sync(self) -> None:
        """Run stitching / sync."""
        if self._sync_result is None:
            QMessageBox.information(
                self,
                "Analyze First",
                "Run Analyze before Sync to detect clip positions.",
            )
            return

        self._set_busy(True, "Syncing...")
        self._worker = _SyncWorker(
            self._track_panel.tracks, self._sync_result, self._config
        )
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_sync_done)
        self._worker.error.connect(self._on_worker_error)
        self._worker.start()

    def _on_sync_done(self) -> None:
        self._set_busy(False)
        n_tracks = len(self._track_panel.tracks)
        self._set_status(f"Synced {n_tracks} track(s) — ready to export.")
        self._update_button_states()

    def _on_reset(self) -> None:
        """Clear all analysis and sync results."""
        self._sync_result = None
        self._track_panel.reset_analysis()
        self._update_waveform()
        self._set_status("Reset — analysis and sync results cleared.")
        self._update_button_states()

    def _on_export(self) -> None:
        """Export synced audio files."""
        tracks = self._track_panel.tracks
        has_synced = any(t.synced_audio is not None for t in tracks)
        if not has_synced:
            QMessageBox.information(
                self,
                "Sync First",
                "Run Analyze and Sync before exporting.",
            )
            return

        dlg = ExportDialog(self._config, len(tracks), self)
        if dlg.exec() != ExportDialog.DialogCode.Accepted:
            return

        output_dir = dlg.output_dir
        config = dlg.config
        os.makedirs(output_dir, exist_ok=True)

        self._set_status("Exporting...")
        QApplication.processEvents()

        exported = 0
        errors = []
        for track in tracks:
            if track.synced_audio is None:
                continue
            safe_name = "".join(c if c.isalnum() or c in " _-" else "_" for c in track.name)
            ext = config.export_format.lower()
            filename = f"{safe_name}_synced.{ext}"
            out_path = os.path.join(output_dir, filename)
            try:
                export_track(track, out_path, config)
                exported += 1
            except Exception as exc:
                errors.append(f"{track.name}: {exc}")
                logger.error("Export error for %s: %s", track.name, exc)

        if errors:
            msg = f"Exported {exported} track(s). Errors:\n" + "\n".join(errors)
            QMessageBox.warning(self, "Export Warnings", msg)
        else:
            self._set_status(f"Exported {exported} track(s) to {output_dir}")
            QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported {exported} synced audio file(s) to:\n{output_dir}",
            )

    # =====================================================================
    #  Worker helpers
    # =====================================================================

    def _on_worker_progress(self, current: int, total: int, message: str) -> None:
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(current)
        self._status_label.setText(message)

    def _on_worker_error(self, error_msg: str) -> None:
        self._set_busy(False)
        self._set_status("Error — see details.")
        QMessageBox.critical(self, "Error", error_msg[:1000])

    # =====================================================================
    #  UI helpers
    # =====================================================================

    def _set_status(self, msg: str) -> None:
        self._status_label.setText(msg)
        logger.info("Status: %s", msg)

    def _set_busy(self, busy: bool, message: str = "") -> None:
        self._progress_bar.setVisible(busy)
        self._progress_bar.setValue(0)
        if message:
            self._status_label.setText(message)

        self._btn_analyze.setEnabled(not busy)
        self._btn_sync.setEnabled(not busy)
        self._btn_reset.setEnabled(not busy)
        self._btn_export.setEnabled(not busy)
        self._btn_add_track.setEnabled(not busy)
        self._btn_add_files.setEnabled(not busy)

    def _update_button_states(self) -> None:
        tracks = self._track_panel.tracks
        has_tracks = len(tracks) > 0
        total_clips = sum(t.clip_count for t in tracks)
        has_clips = total_clips >= 2
        has_analysis = self._sync_result is not None
        has_sync = any(t.synced_audio is not None for t in tracks)

        self._btn_add_files.setEnabled(has_tracks)
        self._btn_remove.setEnabled(has_tracks)
        self._btn_analyze.setEnabled(has_clips)
        self._btn_sync.setEnabled(has_analysis)
        self._btn_reset.setEnabled(has_analysis or has_sync)
        self._btn_export.setEnabled(has_sync)

    def _update_waveform(self, analyzed: bool = False) -> None:
        tracks = self._track_panel.tracks
        sr = self._config.sample_rate or 48000

        if self._sync_result:
            total = self._sync_result.total_timeline_samples
            analyzed = True
        else:
            # Before analysis, estimate total from clip durations
            total = sum(t.total_samples for t in tracks)

        self._waveform.set_data(tracks, sr, total, analyzed=analyzed)

    def _on_tracks_changed(self) -> None:
        # If tracks change, invalidate analysis
        if self._sync_result is not None:
            self._sync_result = None
            for track in self._track_panel.tracks:
                track.synced_audio = None
                for clip in track.clips:
                    clip.analyzed = False
        self._update_waveform()
        self._update_button_states()

    # =====================================================================
    #  Drag-and-drop on window
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

        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and is_supported_file(path):
                paths.append(path)

        if not paths:
            return

        event.acceptProposedAction()

        # Add to selected track, or create new
        track_idx = self._track_panel.selected_track_index()
        if track_idx < 0:
            track_idx = self._track_panel.add_track()

        self._load_files_to_track(track_idx, paths)
