#!/usr/bin/env python3
"""
AudioSync Pro — Multi-device audio/video synchronization tool.

Usage:
    python main.py
"""

import logging
import sys
import os

# Add project root to path so core/app imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Ensure Homebrew and common system paths are in PATH.
# macOS .app bundles launched via Finder don't inherit the shell's PATH,
# so ffmpeg/ffprobe from Homebrew won't be found without this.
_EXTRA_PATHS = [
    "/opt/homebrew/bin",          # Homebrew (Apple Silicon)
    "/usr/local/bin",             # Homebrew (Intel) / MacPorts
    "/opt/homebrew/sbin",
    "/usr/local/sbin",
    "/usr/bin",
    "/bin",
    "/usr/sbin",
    "/sbin",
]
_current_path = os.environ.get("PATH", "")
for p in _EXTRA_PATHS:
    if p not in _current_path and os.path.isdir(p):
        _current_path = p + os.pathsep + _current_path
os.environ["PATH"] = _current_path


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt

    # High-DPI MUST be set before QApplication is created
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    from version import __version__, APP_NAME

    app.setApplicationName(APP_NAME)
    app.setOrganizationName("AudioSync")
    app.setApplicationVersion(__version__)

    from PyQt6.QtGui import QPalette, QColor

    from app.main_window import MainWindow
    from app.theme import STYLESHEET, COLORS

    # Force dark palette globally — ensures ALL widgets have light text
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor(COLORS["bg_deep"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(COLORS["bg_dark"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(COLORS["bg_card"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.BrightText, QColor(COLORS["text_bright"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(COLORS["bg_dark"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(COLORS["accent"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(COLORS["bg_card"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(COLORS["text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(COLORS["text_muted"]))
    palette.setColor(QPalette.ColorRole.Link, QColor(COLORS["accent"]))
    palette.setColor(QPalette.ColorRole.LinkVisited, QColor(COLORS["secondary"]))

    # Disabled state
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.WindowText, QColor(COLORS["text_muted"])
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.Text, QColor(COLORS["text_muted"])
    )
    palette.setColor(
        QPalette.ColorGroup.Disabled,
        QPalette.ColorRole.ButtonText, QColor(COLORS["text_muted"])
    )

    app.setPalette(palette)
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
