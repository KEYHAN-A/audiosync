"""Workflow bar — circular step indicators with glass panel.

Design: frosted-glass bar with circular numbered steps,
cyan glow on active, gradient connector lines, pill action button.
"""

from __future__ import annotations

from enum import IntEnum
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QRectF
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QLinearGradient
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from .theme import COLORS


class Step(IntEnum):
    IMPORT = 0
    ANALYZE = 1
    EXPORT = 2


_STEP_LABELS = {
    Step.IMPORT: "Import",
    Step.ANALYZE: "Analyze & Sync",
    Step.EXPORT: "Export",
}

_STEP_ACTIONS = {
    Step.IMPORT: "Add Files",
    Step.ANALYZE: "Analyze & Sync",
    Step.EXPORT: "Export Audio",
}


class _StepIndicator(QWidget):
    """Circular step indicator with glow effect."""

    def __init__(self, step: Step, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.step = step
        self._state = "future"  # "completed", "current", "future"
        self.setFixedHeight(48)
        self.setMinimumWidth(80)

    def set_state(self, state: str) -> None:
        self._state = state
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        cx = 20
        cy = h // 2
        r = 14

        if self._state == "completed":
            # Filled cyan circle with subtle glow
            glow_color = QColor(COLORS["accent"])
            glow_color.setAlpha(30)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow_color)
            painter.drawEllipse(cx - r - 4, cy - r - 4, (r + 4) * 2, (r + 4) * 2)

            painter.setBrush(QColor(COLORS["accent"]))
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

            text_color = QColor(COLORS["accent"])
            num_color = QColor("#ffffff")
        elif self._state == "current":
            # Bright glow ring
            glow_color = QColor(COLORS["accent"])
            glow_color.setAlpha(25)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow_color)
            painter.drawEllipse(cx - r - 6, cy - r - 6, (r + 6) * 2, (r + 6) * 2)

            # Outer ring
            painter.setPen(QPen(QColor(COLORS["accent"]), 2))
            painter.setBrush(QColor(COLORS["bg_panel"]))
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

            text_color = QColor(COLORS["text_bright"])
            num_color = QColor(COLORS["accent"])
        else:
            # Ghost circle
            painter.setPen(QPen(QColor(COLORS["border_light"]), 1.5))
            painter.setBrush(QColor(COLORS["bg_dark"]))
            painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

            text_color = QColor(COLORS["text_muted"])
            num_color = QColor(COLORS["text_muted"])

        # Number or checkmark
        painter.setPen(num_color)
        font = painter.font()
        font.setPixelSize(12)
        font.setBold(True)
        painter.setFont(font)

        if self._state == "completed":
            # Unicode checkmark
            font.setPixelSize(14)
            painter.setFont(font)
            painter.drawText(cx - r, cy - r, r * 2, r * 2,
                             Qt.AlignmentFlag.AlignCenter, "\u2713")
        else:
            painter.drawText(cx - r, cy - r, r * 2, r * 2,
                             Qt.AlignmentFlag.AlignCenter, str(self.step.value + 1))

        # Label text
        painter.setPen(text_color)
        font.setPixelSize(12)
        font.setBold(self._state == "current")
        painter.setFont(font)
        label_x = cx + r + 8
        painter.drawText(label_x, cy - 8, w - label_x, 16,
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         _STEP_LABELS[self.step])

        painter.end()


class _StepConnector(QWidget):
    """Gradient line connecting two steps."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._active = False
        self.setFixedHeight(48)
        self.setFixedWidth(28)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        y = h // 2

        if self._active:
            grad = QLinearGradient(2, y, w - 2, y)
            grad.setColorAt(0, QColor(COLORS["accent"]))
            grad.setColorAt(1, QColor(COLORS["secondary"]))
            painter.setPen(QPen(grad, 2))
        else:
            painter.setPen(QPen(QColor(COLORS["border_light"]), 1.5))

        painter.drawLine(4, y, w - 4, y)
        painter.end()


class WorkflowBar(QWidget):
    """Glass workflow bar with circular step indicators."""

    action_triggered = pyqtSignal(int)
    nle_export_triggered = pyqtSignal()

    def __init__(
        self,
        nle_available: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setFixedHeight(58)
        self.setProperty("cssClass", "workflow-bar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 5, 20, 5)
        layout.setSpacing(0)

        self._indicators: list[_StepIndicator] = []
        self._connectors: list[_StepConnector] = []

        for step in Step:
            ind = _StepIndicator(step)
            self._indicators.append(ind)
            layout.addWidget(ind)

            if step != Step.EXPORT:
                conn = _StepConnector()
                self._connectors.append(conn)
                layout.addWidget(conn)

        layout.addStretch()

        # Reset button — ghost
        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setProperty("cssClass", "danger")
        self._reset_btn.setFixedHeight(32)
        self._reset_btn.setVisible(False)
        self._reset_btn.clicked.connect(lambda: self.action_triggered.emit(-1))
        layout.addWidget(self._reset_btn)

        # NLE Export button — secondary purple pill
        self._nle_available = nle_available
        self._nle_btn = QPushButton("  Export NLE Timeline  ")
        self._nle_btn.setProperty("cssClass", "secondary")
        self._nle_btn.setFixedHeight(36)
        self._nle_btn.setMinimumWidth(140)
        self._nle_btn.setVisible(False)
        self._nle_btn.clicked.connect(self.nle_export_triggered.emit)
        layout.addWidget(self._nle_btn)

        # Primary action button — solid accent pill
        self._action_btn = QPushButton("Add Files")
        self._action_btn.setProperty("cssClass", "primary")
        self._action_btn.setFixedHeight(36)
        self._action_btn.setMinimumWidth(130)
        self._action_btn.clicked.connect(self._on_action)
        layout.addWidget(self._action_btn)

        self._current_step = Step.IMPORT

    def update_state(
        self,
        total_clips: int,
        has_analysis: bool,
        busy: bool = False,
    ) -> None:
        if has_analysis:
            current = Step.EXPORT
        elif total_clips >= 2:
            current = Step.ANALYZE
        else:
            current = Step.IMPORT

        self._current_step = current

        for i, ind in enumerate(self._indicators):
            step = Step(i)
            if step.value < current.value:
                ind.set_state("completed")
            elif step == current:
                ind.set_state("current")
            else:
                ind.set_state("future")

        for i, conn in enumerate(self._connectors):
            conn.set_active(i < current.value)

        action_text = _STEP_ACTIONS[current]
        self._action_btn.setText(f"  {action_text}  ")
        self._action_btn.setEnabled(not busy)

        self._reset_btn.setVisible(has_analysis)
        self._reset_btn.setEnabled(not busy)

        self._nle_btn.setVisible(
            self._nle_available and has_analysis and not busy
        )
        self._nle_btn.setEnabled(not busy)

    def _on_action(self) -> None:
        self.action_triggered.emit(self._current_step.value)
