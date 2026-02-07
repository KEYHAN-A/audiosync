"""Dialogs — processing screen, export settings, about."""

from __future__ import annotations

import os
import time
from typing import Optional

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.models import SyncConfig
from version import __version__, APP_NAME, GITHUB_URL


# ---------------------------------------------------------------------------
#  Processing Dialog — shown during Analyze / Sync
# ---------------------------------------------------------------------------

class ProcessingDialog(QDialog):
    """
    Modal dialog showing live progress during analysis or sync.

    Features:
    - Progress bar with percentage
    - Current operation label
    - Elapsed / ETA timer
    - Per-clip results table (updated in real-time)
    - Cancel button
    """

    def __init__(
        self,
        title: str = "Processing",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(560, 400)
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowType.WindowCloseButtonHint
        )

        self._cancelled = False
        self._start_time = time.time()

        self._build_ui()

        # Timer for elapsed/ETA updates
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_time)
        self._timer.start(500)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Title
        self._title_label = QLabel("Processing...")
        self._title_label.setProperty("cssClass", "heading")
        layout.addWidget(self._title_label)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setMinimum(0)
        self._progress.setMaximum(100)
        self._progress.setTextVisible(True)
        self._progress.setFixedHeight(24)
        layout.addWidget(self._progress)

        # Operation label
        self._op_label = QLabel("Starting...")
        self._op_label.setProperty("cssClass", "dim")
        layout.addWidget(self._op_label)

        # Time info
        time_row = QHBoxLayout()
        self._elapsed_label = QLabel("Elapsed: 0s")
        self._elapsed_label.setProperty("cssClass", "dim")
        self._eta_label = QLabel("ETA: calculating...")
        self._eta_label.setProperty("cssClass", "dim")
        time_row.addWidget(self._elapsed_label)
        time_row.addStretch()
        time_row.addWidget(self._eta_label)
        layout.addLayout(time_row)

        # Results table
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Clip", "Offset", "Confidence"])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QTableWidget.SelectionMode.NoSelection)
        layout.addWidget(self._table, stretch=1)

        # Cancel button
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setProperty("cssClass", "danger")
        self._cancel_btn.setFixedWidth(120)
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

    # ----- Public API -------------------------------------------------------

    def update_progress(self, current: int, total: int, message: str) -> None:
        """Called from the main thread via signal."""
        if total > 0:
            pct = int((current / total) * 100)
            self._progress.setMaximum(100)
            self._progress.setValue(pct)
        self._op_label.setText(message)
        self._title_label.setText(f"Processing... {self._progress.value()}%")

    def add_clip_result(self, name: str, offset_s: float, confidence: float) -> None:
        """Add a row to the results table."""
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(name))

        if abs(offset_s) < 1.0:
            offset_str = f"{offset_s * 1000:+.1f} ms"
        else:
            offset_str = f"{offset_s:+.2f} s"
        self._table.setItem(row, 1, QTableWidgetItem(offset_str))
        self._table.setItem(row, 2, QTableWidgetItem(f"{confidence:.1f}"))
        self._table.scrollToBottom()

    def finish(self, message: str = "Complete") -> None:
        """Mark processing as done."""
        self._timer.stop()
        self._progress.setValue(100)
        self._title_label.setText(message)
        self._op_label.setText("")
        self._cancel_btn.setText("Close")
        self._cancel_btn.setProperty("cssClass", "")
        self._cancel_btn.style().unpolish(self._cancel_btn)
        self._cancel_btn.style().polish(self._cancel_btn)
        self._cancel_btn.clicked.disconnect()
        self._cancel_btn.clicked.connect(self.accept)

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    # ----- Internal ---------------------------------------------------------

    def _on_cancel(self) -> None:
        self._cancelled = True
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setText("Cancelling...")
        self._op_label.setText("Cancelling — waiting for current operation...")

    def _update_time(self) -> None:
        elapsed = time.time() - self._start_time
        self._elapsed_label.setText(f"Elapsed: {_fmt_time_short(elapsed)}")

        pct = self._progress.value()
        if pct > 0:
            total_est = elapsed / (pct / 100.0)
            remaining = max(0, total_est - elapsed)
            self._eta_label.setText(f"ETA: {_fmt_time_short(remaining)}")
        else:
            self._eta_label.setText("ETA: calculating...")

    def closeEvent(self, event) -> None:
        if not self._cancelled and self._progress.value() < 100:
            event.ignore()
        else:
            event.accept()


# ---------------------------------------------------------------------------
#  Import Progress Dialog
# ---------------------------------------------------------------------------

class ImportProgressDialog(QDialog):
    """Lightweight modal dialog shown while importing files."""

    def __init__(
        self,
        total_files: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Importing Files")
        self.setMinimumWidth(420)
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags()
            & ~Qt.WindowType.WindowCloseButtonHint
        )
        self._cancelled = False

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        self._title_label = QLabel(f"Importing {total_files} file(s)...")
        self._title_label.setProperty("cssClass", "heading")
        layout.addWidget(self._title_label)

        self._progress = QProgressBar()
        self._progress.setMaximum(total_files)
        self._progress.setValue(0)
        self._progress.setFixedHeight(22)
        layout.addWidget(self._progress)

        self._file_label = QLabel("Starting...")
        self._file_label.setProperty("cssClass", "dim")
        layout.addWidget(self._file_label)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setProperty("cssClass", "danger")
        self._cancel_btn.clicked.connect(self._on_cancel)
        btn_row.addWidget(self._cancel_btn)
        layout.addLayout(btn_row)

    def update_file(self, index: int, filename: str) -> None:
        self._progress.setValue(index)
        self._file_label.setText(f"Loading: {filename}")
        self._title_label.setText(
            f"Importing... {index}/{self._progress.maximum()}"
        )

    def finish(self) -> None:
        self.accept()

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    def _on_cancel(self) -> None:
        self._cancelled = True
        self._cancel_btn.setEnabled(False)
        self._cancel_btn.setText("Cancelling...")

    def closeEvent(self, event) -> None:
        if not self._cancelled:
            event.ignore()
        else:
            event.accept()


# ---------------------------------------------------------------------------
#  Export Dialog
# ---------------------------------------------------------------------------

class ExportDialog(QDialog):
    """Dialog for configuring and triggering audio export."""

    def __init__(
        self,
        config: SyncConfig,
        track_count: int,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Synced Audio")
        self.setMinimumWidth(440)
        self._config = config
        self._output_dir: str = ""

        self._build_ui(track_count)

    def _build_ui(self, track_count: int) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        info = QLabel(
            f"Export {track_count} track(s) as individual synced audio files.\n"
            "All files will have the same duration and be perfectly aligned."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Output directory
        dir_group = QGroupBox("Output Directory")
        dir_layout = QHBoxLayout(dir_group)

        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("Choose output folder...")
        self._dir_edit.setReadOnly(True)
        default_dir = os.path.expanduser("~/Desktop/AudioSync Export")
        self._dir_edit.setText(default_dir)
        self._output_dir = default_dir

        dir_btn = QPushButton("Browse...")
        dir_btn.clicked.connect(self._browse_dir)

        dir_layout.addWidget(self._dir_edit, stretch=1)
        dir_layout.addWidget(dir_btn)
        layout.addWidget(dir_group)

        # Format settings
        fmt_group = QGroupBox("Format")
        fmt_layout = QFormLayout(fmt_group)

        self._format_combo = QComboBox()
        self._format_combo.addItems(["WAV", "AIFF", "FLAC"])
        idx = {"wav": 0, "aiff": 1, "flac": 2}.get(self._config.export_format.lower(), 0)
        self._format_combo.setCurrentIndex(idx)
        fmt_layout.addRow("Format:", self._format_combo)

        self._depth_combo = QComboBox()
        self._depth_combo.addItems(["16-bit", "24-bit", "32-bit float"])
        idx = {16: 0, 24: 1, 32: 2}.get(self._config.export_bit_depth, 1)
        self._depth_combo.setCurrentIndex(idx)
        fmt_layout.addRow("Bit Depth:", self._depth_combo)

        sr_label = QLabel(f"{self._config.export_sr or 48000} Hz")
        sr_label.setProperty("cssClass", "dim")
        fmt_layout.addRow("Sample Rate:", sr_label)

        layout.addWidget(fmt_group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Export")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setProperty("cssClass", "accent")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_dir(self) -> None:
        d = QFileDialog.getExistingDirectory(
            self, "Select Output Directory", self._dir_edit.text()
        )
        if d:
            self._dir_edit.setText(d)
            self._output_dir = d

    def _on_accept(self) -> None:
        fmt_map = {0: "wav", 1: "aiff", 2: "flac"}
        self._config.export_format = fmt_map[self._format_combo.currentIndex()]

        depth_map = {0: 16, 1: 24, 2: 32}
        self._config.export_bit_depth = depth_map[self._depth_combo.currentIndex()]

        self._output_dir = self._dir_edit.text()
        self.accept()

    @property
    def output_dir(self) -> str:
        return self._output_dir

    @property
    def config(self) -> SyncConfig:
        return self._config


# ---------------------------------------------------------------------------
#  About Dialog
# ---------------------------------------------------------------------------

class AboutDialog(QDialog):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {APP_NAME}")
        self.setFixedSize(360, 260)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel(APP_NAME)
        title.setProperty("cssClass", "heading")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        ver_label = QLabel(f"Version {__version__}")
        ver_label.setProperty("cssClass", "dim")
        ver_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(ver_label)

        desc = QLabel(
            "Multi-device audio/video synchronization tool.\n"
            "Uses FFT cross-correlation for sample-accurate alignment."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        link = QLabel('<a href="https://keyhan.info" style="color: #38bdf8;">keyhan.info</a>')
        link.setOpenExternalLinks(True)
        link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(link)

        gh_link = QLabel(
            f'<a href="{GITHUB_URL}" style="color: #a78bfa;">GitHub — Open Source</a>'
        )
        gh_link.setOpenExternalLinks(True)
        gh_link.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(gh_link)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _fmt_time_short(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}m {s}s"
