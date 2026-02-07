"""Waveform timeline view — visual representation of clip positions."""

from __future__ import annotations

import numpy as np
from typing import Optional

from PyQt6.QtCore import Qt, QRectF, QPointF, QSize
from PyQt6.QtGui import (
    QColor,
    QFont,
    QLinearGradient,
    QPainter,
    QPen,
    QWheelEvent,
    QMouseEvent,
)
from PyQt6.QtWidgets import QWidget

from core.models import Track
from .theme import COLORS, track_color


class WaveformView(QWidget):
    """
    Custom-painted timeline showing all tracks and their clips.
    Each track gets a horizontal lane with coloured clip blocks.

    Displays contextual empty-state messages depending on app state.
    """

    TRACK_HEIGHT = 64
    TRACK_GAP = 6
    RULER_HEIGHT = 28
    LEFT_MARGIN = 10
    RIGHT_MARGIN = 10
    ENVELOPE_POINTS = 600

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._tracks: list[Track] = []
        self._sample_rate: int = 48000
        self._total_samples: int = 0
        self._analyzed: bool = False
        self._has_clips: bool = False

        self._zoom: float = 1.0
        self._scroll_x: float = 0.0
        self._dragging: bool = False
        self._drag_start: QPointF = QPointF()
        self._scroll_start: float = 0.0

        self.setMinimumHeight(120)
        self.setMouseTracking(True)

    def set_data(
        self,
        tracks: list[Track],
        sample_rate: int,
        total_samples: int,
        analyzed: bool = False,
    ) -> None:
        self._tracks = tracks
        self._sample_rate = max(sample_rate, 1)
        self._total_samples = total_samples
        self._analyzed = analyzed
        self._has_clips = any(t.clip_count > 0 for t in tracks)
        self._fit_view()
        self.update()

    def clear(self) -> None:
        self._tracks = []
        self._total_samples = 0
        self._analyzed = False
        self._has_clips = False
        self.update()

    # ----- Painting ---------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Rounded background matching card aesthetic
        painter.fillRect(0, 0, w, h, QColor(COLORS["bg_dark"]))
        border_pen = QPen(QColor(COLORS["border"]), 1)
        painter.setPen(border_pen)
        painter.drawRoundedRect(0, 0, w - 1, h - 1, 12, 12)

        if not self._tracks:
            self._draw_empty_state(painter, w, h, "no_tracks")
            return

        if not self._has_clips:
            self._draw_empty_state(painter, w, h, "no_clips")
            return

        if not self._analyzed and self._total_samples == 0:
            self._draw_empty_state(painter, w, h, "not_analyzed")
            return

        self._draw_ruler(painter, w)

        y = self.RULER_HEIGHT
        for i, track in enumerate(self._tracks):
            self._draw_track_lane(painter, track, i, y, w, self.TRACK_HEIGHT)
            y += self.TRACK_HEIGHT + self.TRACK_GAP

        painter.end()

    def _draw_empty_state(self, painter: QPainter, w: int, h: int, state: str) -> None:
        messages = {
            "no_tracks": ("Create a track to get started", "Use + Track button or drop files here"),
            "no_clips": ("Import audio or video files into your tracks", "Drag files onto tracks or click + Files"),
            "not_analyzed": ("Click Analyze to detect clip positions", "The timeline will show aligned positions"),
        }
        title, subtitle = messages.get(state, ("Ready", ""))

        # Title
        painter.setPen(QColor(COLORS["text_dim"]))
        font = painter.font()
        font.setPointSize(14)
        font.setBold(True)
        painter.setFont(font)
        title_rect = QRectF(0, h / 2 - 24, w, 24)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, title)

        # Subtitle
        font.setPointSize(11)
        font.setBold(False)
        painter.setFont(font)
        sub_color = QColor(COLORS["text_dim"])
        sub_color.setAlpha(150)
        painter.setPen(sub_color)
        sub_rect = QRectF(0, h / 2 + 4, w, 20)
        painter.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, subtitle)

    def _draw_ruler(self, painter: QPainter, w: int) -> None:
        painter.fillRect(0, 0, w, self.RULER_HEIGHT, QColor(COLORS["bg_panel_solid"]))
        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawLine(0, self.RULER_HEIGHT - 1, w, self.RULER_HEIGHT - 1)

        if self._total_samples == 0:
            return

        total_s = self._total_samples / self._sample_rate
        pps = self._pixels_per_second(w)

        tick_spacings = [0.1, 0.25, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600]
        tick_s = tick_spacings[-1]
        for sp in tick_spacings:
            if sp * pps >= 60:
                tick_s = sp
                break

        font = painter.font()
        font.setPointSize(9)
        font.setFamily("Menlo")
        font.setStyleHint(QFont.StyleHint.Monospace)
        painter.setFont(font)

        t = 0.0
        while t <= total_s:
            x = self._time_to_x(t, w)
            if 0 <= x <= w:
                painter.setPen(QPen(QColor(COLORS["border_light"]), 1))
                painter.drawLine(int(x), self.RULER_HEIGHT - 6, int(x), self.RULER_HEIGHT - 1)
                painter.setPen(QColor(COLORS["text_dim"]))
                painter.drawText(int(x) + 3, self.RULER_HEIGHT - 9, _fmt_time(t))
            t += tick_s

    def _draw_track_lane(
        self, painter: QPainter, track: Track, track_idx: int,
        y: int, w: int, h: int,
    ) -> None:
        color = QColor(track_color(track_idx))

        # Glass lane background with rounded edges
        lane_bg = QColor(COLORS["bg_panel_solid"])
        lane_bg.setAlpha(80)
        lane_rect = QRectF(4, y, w - 8, h)
        painter.setBrush(lane_bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(lane_rect, 8, 8)

        painter.setPen(color)
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        label = track.name
        if track.is_reference:
            label += " [REF]"
        painter.drawText(self.LEFT_MARGIN, y + 14, label)

        if not track.clips:
            painter.setPen(QColor(COLORS["text_dim"]))
            font.setBold(False)
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(self.LEFT_MARGIN, y + 32, "No files")
            return

        clip_y = y + 20
        clip_h = h - 24

        for clip in track.clips:
            if not self._analyzed:
                self._draw_clip_sequential(painter, clip, track_idx, clip_y, clip_h, w)
            else:
                self._draw_clip_positioned(painter, clip, track_idx, clip_y, clip_h, w)

        painter.setPen(QPen(QColor(COLORS["border"]), 1))
        painter.drawLine(0, y + h, w, y + h)

    def _draw_clip_positioned(
        self, painter: QPainter, clip, track_idx: int,
        y: int, h: int, view_w: int,
    ) -> None:
        color = QColor(track_color(track_idx))
        x_start = self._time_to_x(clip.timeline_offset_s, view_w)
        x_end = self._time_to_x(clip.timeline_offset_s + clip.duration_s, view_w)
        clip_w = max(x_end - x_start, 2)
        if x_end < 0 or x_start > view_w:
            return
        self._draw_clip_rect(painter, color, x_start, y, clip_w, h, clip)

    def _draw_clip_sequential(
        self, painter: QPainter, clip, track_idx: int,
        y: int, h: int, view_w: int,
    ) -> None:
        color = QColor(track_color(track_idx))
        track = self._tracks[track_idx]
        total_s = max(sum(c.duration_s for c in track.clips), 0.01)
        offset_s = sum(c.duration_s for c in track.clips[:track.clips.index(clip)])
        pps = (view_w - self.LEFT_MARGIN - self.RIGHT_MARGIN) / total_s
        x_start = self.LEFT_MARGIN + offset_s * pps
        clip_w = max(clip.duration_s * pps, 2)
        self._draw_clip_rect(painter, color, x_start, y, clip_w, h, clip)

    def _draw_clip_rect(
        self, painter: QPainter, color: QColor,
        x: float, y: int, w: float, h: int, clip,
    ) -> None:
        rect = QRectF(x, y, w, h)

        # Rounded gradient fill
        grad = QLinearGradient(x, y, x, y + h)
        c_top = QColor(color)
        c_top.setAlpha(50)
        c_bot = QColor(color)
        c_bot.setAlpha(20)
        grad.setColorAt(0, c_top)
        grad.setColorAt(1, c_bot)
        painter.setBrush(grad)
        painter.setPen(QPen(color, 1))
        painter.drawRoundedRect(rect, 4, 4)

        # Waveform envelope
        if clip.samples is not None and len(clip.samples) > 0 and w > 6:
            self._draw_envelope(painter, clip.samples, color, x, y, w, h)

        # Label
        if w > 50:
            painter.setPen(QColor(COLORS["text"]))
            font = painter.font()
            font.setPointSize(8)
            font.setBold(False)
            painter.setFont(font)
            text_rect = QRectF(x + 4, y + 2, w - 8, 13)
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                clip.name,
            )

    def _draw_envelope(
        self, painter: QPainter, samples: np.ndarray, color: QColor,
        x: float, y: int, w: float, h: int,
    ) -> None:
        n = len(samples)
        num_bins = min(int(w), self.ENVELOPE_POINTS, n)
        if num_bins < 2:
            return

        bin_size = n / num_bins
        mid_y = y + h / 2

        env_color = QColor(color)
        env_color.setAlpha(120)
        painter.setPen(Qt.PenStyle.NoPen)

        for i in range(num_bins):
            start_idx = int(i * bin_size)
            end_idx = min(int((i + 1) * bin_size), n)
            if start_idx >= end_idx:
                continue

            chunk = samples[start_idx:end_idx]
            peak = float(np.max(np.abs(chunk)))
            bar_h = peak * (h / 2 - 3)

            bx = x + (i / num_bins) * w
            bw = max(w / num_bins, 1)
            painter.fillRect(QRectF(bx, mid_y - bar_h, bw, bar_h * 2), env_color)

    # ----- View helpers -----------------------------------------------------

    def _pixels_per_second(self, view_w: int) -> float:
        total_s = self._total_samples / self._sample_rate if self._total_samples > 0 else 1
        usable = view_w - self.LEFT_MARGIN - self.RIGHT_MARGIN
        return (usable / total_s) * self._zoom

    def _time_to_x(self, time_s: float, view_w: int) -> float:
        pps = self._pixels_per_second(view_w)
        return self.LEFT_MARGIN + (time_s - self._scroll_x) * pps

    def _fit_view(self) -> None:
        self._zoom = 1.0
        self._scroll_x = 0.0

    # ----- Interaction ------------------------------------------------------

    def wheelEvent(self, event: QWheelEvent) -> None:
        delta = event.angleDelta().y()
        if delta > 0:
            self._zoom = min(self._zoom * 1.15, 100.0)
        else:
            self._zoom = max(self._zoom / 1.15, 0.1)
        self.update()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_start = event.position()
            self._scroll_start = self._scroll_x

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._dragging:
            dx = event.position().x() - self._drag_start.x()
            pps = self._pixels_per_second(self.width())
            if pps > 0:
                self._scroll_x = self._scroll_start - dx / pps
                self._scroll_x = max(0, self._scroll_x)
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._dragging = False

    def sizeHint(self) -> QSize:
        n_tracks = max(len(self._tracks), 2)
        h = self.RULER_HEIGHT + n_tracks * (self.TRACK_HEIGHT + self.TRACK_GAP) + 10
        return QSize(600, h)


def _fmt_time(seconds: float) -> str:
    total_s = int(seconds)
    m = total_s // 60
    s = total_s % 60
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{m}:{s:02d}"
