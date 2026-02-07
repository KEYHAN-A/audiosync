"""Dialogs — export settings and about."""

from __future__ import annotations

import os
from typing import Optional

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.models import SyncConfig


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
        layout.setSpacing(12)

        # --- Info ---
        info = QLabel(
            f"Export {track_count} track(s) as individual synced audio files.\n"
            "All files will have the same duration and be perfectly aligned."
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # --- Output directory ---
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

        # --- Format settings ---
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

        sr_label = QLabel(f"{self._config.sample_rate or 48000} Hz")
        sr_label.setProperty("cssClass", "dim")
        fmt_layout.addRow("Sample Rate:", sr_label)

        layout.addWidget(fmt_group)

        # --- Buttons ---
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
        # Update config from UI
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
    """Simple about dialog."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About AudioSync Pro")
        self.setFixedSize(360, 200)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("AudioSync Pro")
        title.setProperty("cssClass", "heading")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version = QLabel("Version 1.0.0")
        version.setProperty("cssClass", "dim")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version)

        desc = QLabel(
            "Multi-device audio/video synchronization tool.\n"
            "Uses FFT cross-correlation for sample-accurate alignment."
        )
        desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(desc)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
