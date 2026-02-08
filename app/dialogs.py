"""Dialogs — processing, export, timeline export, device auth, cloud projects, about."""

from __future__ import annotations

import logging
import os
import time
import webbrowser
from typing import Optional

from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal
from PyQt6.QtWidgets import (
    QApplication,
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
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.models import SyncConfig
from version import __version__, APP_NAME, GITHUB_URL

logger = logging.getLogger("audiosync.dialogs")

# Defensive import — opentimelineio may not be available in all builds
try:
    from core.timeline_export import get_supported_formats
    TIMELINE_EXPORT_AVAILABLE = True
except ImportError:
    TIMELINE_EXPORT_AVAILABLE = False

    def get_supported_formats():
        return {}  # fallback


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
        self._format_combo.addItems(["WAV", "AIFF", "FLAC", "MP3"])
        idx = {"wav": 0, "aiff": 1, "flac": 2, "mp3": 3}.get(
            self._config.export_format.lower(), 0
        )
        self._format_combo.setCurrentIndex(idx)
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)
        fmt_layout.addRow("Format:", self._format_combo)

        # Bit depth (for lossless formats)
        self._depth_combo = QComboBox()
        self._depth_combo.addItems(["16-bit", "24-bit", "32-bit float"])
        idx = {16: 0, 24: 1, 32: 2}.get(self._config.export_bit_depth, 1)
        self._depth_combo.setCurrentIndex(idx)
        self._depth_label = QLabel("Bit Depth:")
        fmt_layout.addRow(self._depth_label, self._depth_combo)

        # Bitrate (for lossy formats like MP3)
        self._bitrate_combo = QComboBox()
        self._bitrate_combo.addItems(["128 kbps", "192 kbps", "256 kbps", "320 kbps"])
        bitrate_idx = {128: 0, 192: 1, 256: 2, 320: 3}.get(
            self._config.export_bitrate_kbps, 3
        )
        self._bitrate_combo.setCurrentIndex(bitrate_idx)
        self._bitrate_label = QLabel("Bitrate:")
        fmt_layout.addRow(self._bitrate_label, self._bitrate_combo)

        sr_label = QLabel(f"{self._config.export_sr or 48000} Hz")
        sr_label.setProperty("cssClass", "dim")
        fmt_layout.addRow("Sample Rate:", sr_label)

        layout.addWidget(fmt_group)

        # Set initial visibility based on current format
        self._on_format_changed(self._format_combo.currentIndex())

        # Drift correction option
        from PyQt6.QtWidgets import QCheckBox
        self._drift_check = QCheckBox("Correct clock drift between devices")
        self._drift_check.setChecked(self._config.drift_correction)
        self._drift_check.setToolTip(
            "Automatically compensate for sample clock differences between "
            "recording devices, keeping audio aligned for the full duration."
        )
        layout.addWidget(self._drift_check)

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

    def _on_format_changed(self, index: int) -> None:
        """Toggle between bit depth (lossless) and bitrate (lossy) controls."""
        is_mp3 = index == 3  # MP3
        self._depth_label.setVisible(not is_mp3)
        self._depth_combo.setVisible(not is_mp3)
        self._bitrate_label.setVisible(is_mp3)
        self._bitrate_combo.setVisible(is_mp3)

    def _on_accept(self) -> None:
        fmt_map = {0: "wav", 1: "aiff", 2: "flac", 3: "mp3"}
        self._config.export_format = fmt_map[self._format_combo.currentIndex()]

        depth_map = {0: 16, 1: 24, 2: 32}
        self._config.export_bit_depth = depth_map[self._depth_combo.currentIndex()]

        bitrate_map = {0: 128, 1: 192, 2: 256, 3: 320}
        self._config.export_bitrate_kbps = bitrate_map[self._bitrate_combo.currentIndex()]

        self._config.drift_correction = self._drift_check.isChecked()

        self._output_dir = self._dir_edit.text()
        self.accept()

    @property
    def output_dir(self) -> str:
        return self._output_dir

    @property
    def config(self) -> SyncConfig:
        return self._config


# ---------------------------------------------------------------------------
#  Timeline Export Dialog — export for DaVinci Resolve / NLEs
# ---------------------------------------------------------------------------

class TimelineExportDialog(QDialog):
    """Dialog for exporting the analysed timeline for DaVinci Resolve / NLEs."""

    def __init__(
        self,
        track_count: int,
        clip_count: int,
        timeline_s: float,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Timeline for NLE")
        self.setMinimumWidth(480)
        self._output_path: str = ""
        self._frame_rate: float = 24.0
        self._timeline_name: str = "AudioSync Pro"

        self._build_ui(track_count, clip_count, timeline_s)

    def _build_ui(self, track_count: int, clip_count: int, timeline_s: float) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        # Info
        dur_str = f"{timeline_s:.1f}s"
        info = QLabel(
            f"Export {track_count} track(s) with {clip_count} analysed clip(s) "
            f"({dur_str} timeline) as an NLE timeline file.\n\n"
            "Clips will reference your original media files so DaVinci Resolve, "
            "Final Cut Pro, or Premiere can relink and arrange them on a timeline."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # Timeline name
        name_group = QGroupBox("Timeline Name")
        name_layout = QHBoxLayout(name_group)
        self._name_edit = QLineEdit("AudioSync Pro")
        name_layout.addWidget(self._name_edit)
        layout.addWidget(name_group)

        # Format selection
        fmt_group = QGroupBox("Format")
        fmt_layout = QFormLayout(fmt_group)

        self._format_combo = QComboBox()
        formats = get_supported_formats()
        for ext, desc in formats.items():
            self._format_combo.addItem(f"{ext}  —  {desc}", ext)
        self._format_combo.setCurrentIndex(0)  # .otio default
        fmt_layout.addRow("Format:", self._format_combo)

        self._fps_spin = QSpinBox()
        self._fps_spin.setRange(1, 120)
        self._fps_spin.setValue(24)
        self._fps_spin.setSuffix(" fps")
        fmt_layout.addRow("Frame Rate:", self._fps_spin)

        layout.addWidget(fmt_group)

        # Output file
        file_group = QGroupBox("Output File")
        file_layout = QHBoxLayout(file_group)

        default_path = os.path.join(
            os.path.expanduser("~/Desktop"),
            "AudioSync Pro Timeline.fcpxml",
        )
        self._file_edit = QLineEdit(default_path)
        self._file_edit.setReadOnly(True)

        file_btn = QPushButton("Browse...")
        file_btn.clicked.connect(self._browse_file)

        file_layout.addWidget(self._file_edit, stretch=1)
        file_layout.addWidget(file_btn)
        layout.addWidget(file_group)

        # Update filename extension when format changes
        self._format_combo.currentIndexChanged.connect(self._on_format_changed)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Export Timeline")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setProperty("cssClass", "accent")
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse_file(self) -> None:
        ext = self._format_combo.currentData()
        filters = {
            ".otio": "OpenTimelineIO (*.otio)",
            ".fcpxml": "Final Cut Pro XML (*.fcpxml)",
            ".edl": "Edit Decision List (*.edl)",
        }
        selected_filter = filters.get(ext, "All Files (*)")

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Timeline",
            self._file_edit.text(),
            ";;".join(filters.values()),
            selected_filter,
        )
        if path:
            self._file_edit.setText(path)

    def _on_format_changed(self) -> None:
        ext = self._format_combo.currentData()
        current = self._file_edit.text()
        if current:
            base = os.path.splitext(current)[0]
            self._file_edit.setText(base + ext)

    def _on_accept(self) -> None:
        self._output_path = self._file_edit.text()
        self._frame_rate = float(self._fps_spin.value())
        self._timeline_name = self._name_edit.text() or "AudioSync Pro"
        self.accept()

    @property
    def output_path(self) -> str:
        return self._output_path

    @property
    def frame_rate(self) -> float:
        return self._frame_rate

    @property
    def timeline_name(self) -> str:
        return self._timeline_name


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
#  Device Auth Dialog — sign in from the desktop via device-code flow
# ---------------------------------------------------------------------------

class _DevicePollWorker(QThread):
    """Background thread that polls the device token endpoint."""

    success = pyqtSignal(dict)   # {token, user}
    error = pyqtSignal(str)

    def __init__(self, cloud_client, device_code: str, interval: int) -> None:
        super().__init__()
        self._cloud = cloud_client
        self._device_code = device_code
        self._interval = interval
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    def run(self) -> None:
        from core.cloud import CloudError
        try:
            start = time.time()
            while not self._stop and (time.time() - start) < 600:
                result = self._cloud._request("POST", "/auth/device/token", body={
                    "device_code": self._device_code,
                })
                if result.get("success") and result.get("token"):
                    self._cloud.set_token(result["token"])
                    self.success.emit(result)
                    return
                error = result.get("error", "")
                if error == "expired":
                    self.error.emit("Device code expired. Please try again.")
                    return
                if error == "authorization_pending":
                    time.sleep(self._interval)
                    continue
                self.error.emit(f"Unexpected: {error}")
                return
            if not self._stop:
                self.error.emit("Timed out waiting for authorization.")
        except CloudError as exc:
            self.error.emit(str(exc))
        except Exception as exc:
            self.error.emit(f"Error: {exc}")


class DeviceAuthDialog(QDialog):
    """
    Modal dialog for the device-code OAuth flow.

    Shows the user_code prominently, offers a button to open the browser,
    and polls for authorization in a background thread.
    """

    auth_success = pyqtSignal(dict)  # emits user info on successful auth

    def __init__(self, cloud_client, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sign In to AudioSync Cloud")
        self.setMinimumSize(420, 320)
        self.setModal(True)
        self._cloud = cloud_client
        self._worker: Optional[_DevicePollWorker] = None
        self._device_code: Optional[str] = None
        self._verification_uri: Optional[str] = None

        self._build_ui()
        self._start_flow()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(32, 28, 32, 24)

        title = QLabel("Sign In")
        title.setProperty("cssClass", "heading")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        desc = QLabel(
            "Enter this code on the web to authorize\n"
            "your desktop app with your Google account."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setProperty("cssClass", "dim")
        layout.addWidget(desc)

        # User code — large and prominent
        self._code_label = QLabel("--------")
        self._code_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._code_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._code_label.setStyleSheet(
            "font-size: 32px; font-weight: 700; letter-spacing: 6px; "
            "color: #67e8f9; padding: 16px; "
            "background: rgba(6, 182, 212, 0.08); "
            "border: 1px solid rgba(6, 182, 212, 0.20); "
            "border-radius: 16px;"
        )
        layout.addWidget(self._code_label)

        # Copy + Open browser buttons
        btn_row = QHBoxLayout()
        self._copy_btn = QPushButton("Copy Code")
        self._copy_btn.clicked.connect(self._copy_code)
        self._copy_btn.setEnabled(False)
        btn_row.addWidget(self._copy_btn)

        self._open_btn = QPushButton("Open studio.keyhan.info")
        self._open_btn.setProperty("cssClass", "accent")
        self._open_btn.clicked.connect(self._open_browser)
        self._open_btn.setEnabled(False)
        btn_row.addWidget(self._open_btn)
        layout.addLayout(btn_row)

        # Verification URL hint
        self._url_label = QLabel("")
        self._url_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._url_label.setStyleSheet(
            "font-size: 11px; color: #94a3b8; padding: 0;"
        )
        layout.addWidget(self._url_label)

        # Retry button (hidden by default, shown on error)
        self._retry_btn = QPushButton("Retry")
        self._retry_btn.setProperty("cssClass", "accent")
        self._retry_btn.clicked.connect(self._retry_flow)
        self._retry_btn.setVisible(False)
        layout.addWidget(self._retry_btn)

        # Status
        self._status_label = QLabel("Requesting code...")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setProperty("cssClass", "dim")
        self._status_label.setWordWrap(True)
        layout.addWidget(self._status_label)

        # Registration hint
        self._register_label = QLabel(
            'Don\'t have an account? '
            '<a href="https://studio.keyhan.info/register" '
            'style="color: #67e8f9;">Create one free</a>'
        )
        self._register_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._register_label.setOpenExternalLinks(True)
        self._register_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
        layout.addWidget(self._register_label)

        layout.addStretch()

        # Cancel
        cancel_row = QHBoxLayout()
        cancel_row.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.setProperty("cssClass", "danger")
        self._cancel_btn.clicked.connect(self._on_cancel)
        cancel_row.addWidget(self._cancel_btn)
        layout.addLayout(cancel_row)

    def _start_flow(self) -> None:
        """Request a device code from the API."""
        # Reset UI to loading state
        self._code_label.setText("--------")
        self._code_label.setStyleSheet(
            "font-size: 32px; font-weight: 700; letter-spacing: 6px; "
            "color: #67e8f9; padding: 16px; "
            "background: rgba(6, 182, 212, 0.08); "
            "border: 1px solid rgba(6, 182, 212, 0.20); "
            "border-radius: 16px;"
        )
        self._copy_btn.setEnabled(False)
        self._copy_btn.setVisible(True)
        self._open_btn.setEnabled(False)
        self._open_btn.setVisible(True)
        self._retry_btn.setVisible(False)
        self._url_label.setText("")
        self._register_label.setVisible(True)
        self._status_label.setText("Requesting code...")
        self._status_label.setStyleSheet("")

        try:
            result = self._cloud.start_device_flow()
            self._device_code = result.get("device_code")
            user_code = result.get("user_code", "????-????")
            self._verification_uri = result.get("verification_uri", "")

            self._code_label.setText(user_code)
            self._copy_btn.setEnabled(True)
            self._open_btn.setEnabled(True)
            self._status_label.setText("Waiting for authorization...")

            # Show the verification URL so users know the destination
            if self._verification_uri:
                # Strip https:// for a cleaner display
                display_url = self._verification_uri.replace("https://", "")
                self._url_label.setText(display_url)
            else:
                self._url_label.setText("")

            # Start polling
            interval = result.get("interval", 5)
            self._worker = _DevicePollWorker(self._cloud, self._device_code, interval)
            self._worker.success.connect(self._on_auth_success)
            self._worker.error.connect(self._on_auth_error)
            self._worker.start()

        except Exception as exc:
            self._code_label.setVisible(False)
            self._copy_btn.setVisible(False)
            self._open_btn.setVisible(False)
            self._retry_btn.setVisible(True)
            self._status_label.setText(
                f"Could not start sign-in: {exc}\n\n"
                "Please check your internet connection and try again."
            )
            self._status_label.setStyleSheet("color: #f87171;")
            logger.error("Device flow start failed: %s", exc)

    def _copy_code(self) -> None:
        code = self._code_label.text()
        clipboard = QApplication.clipboard()
        if clipboard:
            clipboard.setText(code)
        self._copy_btn.setText("Copied!")
        QTimer.singleShot(2000, lambda: self._copy_btn.setText("Copy Code"))

    def _retry_flow(self) -> None:
        """Reset UI and retry the device code flow."""
        self._code_label.setVisible(True)
        self._start_flow()

    def _open_browser(self) -> None:
        if self._verification_uri:
            code = self._code_label.text()
            url = f"{self._verification_uri}?code={code}"
            webbrowser.open(url)

    def _on_auth_success(self, result: dict) -> None:
        user = result.get("user", {})
        name = user.get("name", user.get("email", "User"))
        self._status_label.setText(f"Signed in as {name}")
        self._status_label.setStyleSheet("color: #34d399; font-size: 13px; font-weight: 600;")
        self._code_label.setText("\u2713")
        self._code_label.setStyleSheet(
            "font-size: 48px; font-weight: 700; color: #34d399; padding: 16px; "
            "background: rgba(52, 211, 153, 0.08); "
            "border: 1px solid rgba(52, 211, 153, 0.20); "
            "border-radius: 16px;"
        )
        self._copy_btn.setVisible(False)
        self._open_btn.setVisible(False)
        self._cancel_btn.setText("Done")
        self._cancel_btn.setProperty("cssClass", "accent")
        self._cancel_btn.style().unpolish(self._cancel_btn)
        self._cancel_btn.style().polish(self._cancel_btn)
        self._cancel_btn.clicked.disconnect()
        self._cancel_btn.clicked.connect(self.accept)
        self.auth_success.emit(user)

    def _on_auth_error(self, message: str) -> None:
        self._status_label.setText(message)
        self._status_label.setStyleSheet("color: #f87171;")
        self._retry_btn.setVisible(True)

    def _on_cancel(self) -> None:
        if self._worker:
            self._worker.stop()
            self._worker.wait(2000)
        self.reject()

    def closeEvent(self, event) -> None:
        if self._worker:
            self._worker.stop()
            self._worker.wait(2000)
        event.accept()


# ---------------------------------------------------------------------------
#  Cloud Projects Dialog — list / open / delete / save cloud projects
# ---------------------------------------------------------------------------

class _CloudWorker(QThread):
    """Background thread for cloud operations."""

    result = pyqtSignal(object)   # result data
    error = pyqtSignal(str)

    def __init__(self, func, *args) -> None:
        super().__init__()
        self._func = func
        self._args = args

    def run(self) -> None:
        try:
            r = self._func(*self._args)
            self.result.emit(r)
        except Exception as exc:
            self.error.emit(str(exc))


class CloudProjectsDialog(QDialog):
    """
    Dialog for managing cloud projects.

    - Table showing all projects (name, description, updated_at)
    - Open / Delete / Save buttons
    """

    project_opened = pyqtSignal(dict)   # emits full project data when user opens one

    def __init__(
        self,
        cloud_client,
        has_current_project: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Cloud Projects")
        self.setMinimumSize(620, 440)
        self.setModal(True)
        self._cloud = cloud_client
        self._has_current = has_current_project
        self._projects: list[dict] = []
        self._worker: Optional[_CloudWorker] = None

        self._build_ui()
        self._load_projects()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel("Cloud Projects")
        title.setProperty("cssClass", "heading")
        layout.addWidget(title)

        # Table
        self._table = QTableWidget(0, 3)
        self._table.setHorizontalHeaderLabels(["Name", "Description", "Last Updated"])
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        layout.addWidget(self._table, stretch=1)

        # Status
        self._status_label = QLabel("Loading...")
        self._status_label.setProperty("cssClass", "dim")
        layout.addWidget(self._status_label)

        # Buttons
        btn_row = QHBoxLayout()

        self._open_btn = QPushButton("Open")
        self._open_btn.setProperty("cssClass", "accent")
        self._open_btn.setEnabled(False)
        self._open_btn.clicked.connect(self._on_open)
        btn_row.addWidget(self._open_btn)

        self._delete_btn = QPushButton("Delete")
        self._delete_btn.setProperty("cssClass", "danger")
        self._delete_btn.setEnabled(False)
        self._delete_btn.clicked.connect(self._on_delete)
        btn_row.addWidget(self._delete_btn)

        btn_row.addStretch()

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._load_projects)
        btn_row.addWidget(self._refresh_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

        # Selection change
        self._table.itemSelectionChanged.connect(self._on_selection_changed)

    def _load_projects(self) -> None:
        self._status_label.setText("Loading projects...")
        self._table.setRowCount(0)
        self._open_btn.setEnabled(False)
        self._delete_btn.setEnabled(False)

        self._worker = _CloudWorker(self._cloud.list_projects)
        self._worker.result.connect(self._on_projects_loaded)
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    def _on_projects_loaded(self, projects) -> None:
        self._projects = projects if projects else []
        self._table.setRowCount(len(self._projects))

        for i, proj in enumerate(self._projects):
            self._table.setItem(i, 0, QTableWidgetItem(proj.get("name", "")))
            self._table.setItem(i, 1, QTableWidgetItem(proj.get("description", "")))
            updated = proj.get("updated_at", "")
            if updated:
                # Show just date + time
                updated = updated.replace("T", " ").split(".")[0]
            self._table.setItem(i, 2, QTableWidgetItem(updated))

        count = len(self._projects)
        self._status_label.setText(
            f"{count} project{'s' if count != 1 else ''}" if count > 0
            else "No cloud projects yet"
        )

    def _on_load_error(self, message: str) -> None:
        self._status_label.setText(f"Error: {message}")

    def _on_selection_changed(self) -> None:
        has_selection = len(self._table.selectedItems()) > 0
        self._open_btn.setEnabled(has_selection)
        self._delete_btn.setEnabled(has_selection)

    def _on_open(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._projects):
            return

        project_id = self._projects[row].get("id")
        self._status_label.setText("Downloading project...")
        self._open_btn.setEnabled(False)

        self._worker = _CloudWorker(self._cloud.load_project, project_id)
        self._worker.result.connect(self._on_project_downloaded)
        self._worker.error.connect(self._on_load_error)
        self._worker.start()

    def _on_project_downloaded(self, project: dict) -> None:
        self._status_label.setText("Project loaded.")
        self.project_opened.emit(project)
        self.accept()

    def _on_delete(self) -> None:
        row = self._table.currentRow()
        if row < 0 or row >= len(self._projects):
            return

        name = self._projects[row].get("name", "this project")
        reply = QMessageBox.question(
            self, "Delete Project",
            f"Are you sure you want to delete \"{name}\" from the cloud?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        project_id = self._projects[row].get("id")
        self._status_label.setText("Deleting...")

        self._worker = _CloudWorker(self._cloud.delete_project, project_id)
        self._worker.result.connect(lambda _: self._load_projects())
        self._worker.error.connect(self._on_load_error)
        self._worker.start()


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _fmt_time_short(seconds: float) -> str:
    if seconds < 60:
        return f"{int(seconds)}s"
    m = int(seconds) // 60
    s = int(seconds) % 60
    return f"{m}m {s}s"
