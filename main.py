#!/usr/bin/env python3
"""
AudioSync Pro — Multi-device audio/video synchronization tool.

Synchronizes audio from multiple recording devices (cameras, mics,
Zoom recorders) using FFT cross-correlation. Exports perfectly aligned
audio files — one per device track.

Usage:
    python main.py
"""

import logging
import sys
import os

# Add project root to path so core/app imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main() -> None:
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt

    from app.main_window import MainWindow
    from app.theme import STYLESHEET

    app = QApplication(sys.argv)
    app.setApplicationName("AudioSync Pro")
    app.setOrganizationName("AudioSync")
    app.setApplicationVersion("1.0.0")

    # Apply dark theme
    app.setStyleSheet(STYLESHEET)

    # High-DPI support
    app.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
