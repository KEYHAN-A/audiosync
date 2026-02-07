"""Workflow bar — step indicator with contextual next-action button."""

from __future__ import annotations

from enum import IntEnum
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QPainter, QPen
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
    SYNC = 2
    EXPORT = 3


_STEP_LABELS = {
    Step.IMPORT: "Import",
    Step.ANALYZE: "Analyze",
    Step.SYNC: "Sync",
    Step.EXPORT: "Export",
}

_STEP_ACTIONS = {
    Step.IMPORT: "Add Files",
    Step.ANALYZE: "Analyze",
    Step.SYNC: "Sync",
    Step.EXPORT: "Export",
}


class _StepIndicator(QWidget):
    """Individual step circle + label, painted custom."""

    def __init__(self, step: Step, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.step = step
        self._state = "future"  # "completed", "current", "future"
        self.setFixedHeight(40)
        self.setMinimumWidth(70)

    def set_state(self, state: str) -> None:
        self._state = state
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()

        # Circle
        cx = 16
        cy = h // 2
        r = 10

        if self._state == "completed":
            circle_color = QColor(COLORS["accent"])
            text_color = QColor(COLORS["accent"])
            num_color = QColor("#ffffff")
        elif self._state == "current":
            circle_color = QColor(COLORS["accent"])
            text_color = QColor(COLORS["text_bright"])
            num_color = QColor("#ffffff")
        else:
            circle_color = QColor(COLORS["border_light"])
            text_color = QColor(COLORS["text_dim"])
            num_color = QColor(COLORS["text_dim"])

        # Draw circle
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(circle_color)
        painter.drawEllipse(cx - r, cy - r, r * 2, r * 2)

        # Number or checkmark
        painter.setPen(num_color)
        font = painter.font()
        font.setPixelSize(11)
        font.setBold(True)
        painter.setFont(font)

        if self._state == "completed":
            painter.drawText(cx - r, cy - r, r * 2, r * 2,
                             Qt.AlignmentFlag.AlignCenter, "\u2713")
        else:
            painter.drawText(cx - r, cy - r, r * 2, r * 2,
                             Qt.AlignmentFlag.AlignCenter, str(self.step.value + 1))

        # Label
        painter.setPen(text_color)
        font.setPixelSize(12)
        font.setBold(self._state == "current")
        painter.setFont(font)
        label_x = cx + r + 6
        painter.drawText(label_x, cy - 8, w - label_x, 16,
                         Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                         _STEP_LABELS[self.step])

        painter.end()


class _StepConnector(QWidget):
    """Thin line connecting two steps."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._active = False
        self.setFixedHeight(40)
        self.setFixedWidth(24)

    def set_active(self, active: bool) -> None:
        self._active = active
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        y = h // 2

        color = QColor(COLORS["accent"]) if self._active else QColor(COLORS["border_light"])
        painter.setPen(QPen(color, 2))
        painter.drawLine(2, y, w - 2, y)
        painter.end()


class WorkflowBar(QWidget):
    """
    Horizontal workflow step indicator with a contextual action button.

    Steps: Import -> Analyze -> Sync -> Export
    """

    action_triggered = pyqtSignal(int)  # Step enum value

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFixedHeight(52)
        self.setProperty("cssClass", "workflow-bar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 6, 16, 6)
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

        # Reset button (small, ghost style)
        self._reset_btn = QPushButton("Reset")
        self._reset_btn.setProperty("cssClass", "danger")
        self._reset_btn.setFixedHeight(30)
        self._reset_btn.setVisible(False)
        self._reset_btn.clicked.connect(lambda: self.action_triggered.emit(-1))
        layout.addWidget(self._reset_btn)

        # Primary action button
        self._action_btn = QPushButton("Add Files")
        self._action_btn.setProperty("cssClass", "primary")
        self._action_btn.setFixedHeight(34)
        self._action_btn.setMinimumWidth(120)
        self._action_btn.clicked.connect(self._on_action)
        layout.addWidget(self._action_btn)

        self._current_step = Step.IMPORT

    def update_state(
        self,
        total_clips: int,
        has_analysis: bool,
        has_sync: bool,
        busy: bool = False,
    ) -> None:
        """Refresh the step indicator based on app state."""
        if has_sync:
            current = Step.EXPORT
        elif has_analysis:
            current = Step.SYNC
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

        # Update action button
        action_text = _STEP_ACTIONS[current]
        self._action_btn.setText(f"  {action_text}  ")
        self._action_btn.setEnabled(not busy)

        # Show reset button when analysis exists
        self._reset_btn.setVisible(has_analysis or has_sync)
        self._reset_btn.setEnabled(not busy)

    def _on_action(self) -> None:
        self.action_triggered.emit(self._current_step.value)
