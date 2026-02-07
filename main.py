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

    from app.main_window import MainWindow
    from app.theme import STYLESHEET

    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
