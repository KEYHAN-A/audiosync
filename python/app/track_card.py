"""Track card system — glassmorphism media-folder cards.

Design: frosted-glass cards with media folder aesthetics,
circular badges, pill-shaped metadata, generous spacing.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QRectF, QSize, QPoint
from PyQt6.QtGui import (
    QColor, QFont, QPainter, QPen, QPainterPath, QCursor,
    QDragEnterEvent, QDragMoveEvent, QDropEvent, QLinearGradient,
)
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
    QGraphicsDropShadowEffect,
)

from core.audio_io import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, is_supported_file
from core.models import Clip, Track

from .theme import COLORS, track_color


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _fmt_duration(seconds: float) -> str:
    if seconds <= 0:
        return "0:00"
    total_s = int(seconds)
    h = total_s // 3600
    m = (total_s % 3600) // 60
    s = total_s % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


def _fmt_offset(seconds: float) -> str:
    if abs(seconds) < 0.001:
        return "0 ms"
    if abs(seconds) < 1.0:
        return f"{seconds * 1000:+.1f} ms"
    return f"{seconds:+.2f} s"


def _fmt_creation_date(timestamp: float) -> str:
    try:
        dt = datetime.fromtimestamp(timestamp)
        now = datetime.now()
        if dt.year == now.year:
            return dt.strftime("%b %d, %I:%M %p")
        return dt.strftime("%b %d %Y, %I:%M %p")
    except (ValueError, OSError):
        return ""


def _get_track_time_span(track: Track) -> str:
    times = [(c.creation_time, c.duration_s) for c in track.clips if c.creation_time]
    if not times:
        return ""
    try:
        earliest = min(t[0] for t in times)
        latest = max(t[0] + t[1] for t in times)
        dt_start = datetime.fromtimestamp(earliest)
        dt_end = datetime.fromtimestamp(latest)
        if dt_start.date() == dt_end.date():
            return f"{dt_start.strftime('%I:%M')}\u2013{dt_end.strftime('%I:%M %p')}"
        return f"{dt_start.strftime('%b %d %I:%M')}\u2013{dt_end.strftime('%b %d %I:%M %p')}"
    except (ValueError, OSError):
        return ""


def _glow_shadow(color: str, blur: int = 20, alpha: int = 40) -> QGraphicsDropShadowEffect:
    """Create a subtle glow shadow effect."""
    effect = QGraphicsDropShadowEffect()
    c = QColor(color)
    c.setAlpha(alpha)
    effect.setColor(c)
    effect.setBlurRadius(blur)
    effect.setOffset(0, 2)
    return effect


# ---------------------------------------------------------------------------
#  ClipRow — single file pill inside a track card
# ---------------------------------------------------------------------------

class ClipRow(QFrame):
    """Minimal row displaying one clip inside a track card."""

    removed = pyqtSignal(int)

    def __init__(
        self, clip: Clip, index: int, color: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._clip = clip
        self._index = index
        self._color = color
        self.setObjectName("ClipRow")
        self.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_menu)
        self.setFixedHeight(38)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 10, 0)
        layout.setSpacing(10)

        # Circular type badge
        badge_text = "\U0001F3AC" if clip.is_video else "\U0001F3B5"
        badge = QLabel(badge_text)
        badge.setFixedSize(26, 26)
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge_bg = COLORS["secondary_subtle"] if clip.is_video else COLORS["accent_subtle"]
        badge.setStyleSheet(
            f"background: {badge_bg}; "
            f"border-radius: 13px; font-size: 12px; border: none;"
        )
        layout.addWidget(badge)

        # File name
        name_lbl = QLabel(clip.name)
        name_lbl.setStyleSheet(
            f"color: {COLORS['text']}; font-size: 12px; font-weight: 500; border: none;"
        )
        layout.addWidget(name_lbl, stretch=1)

        # Creation date (compact)
        if clip.creation_time:
            date_lbl = QLabel(_fmt_creation_date(clip.creation_time))
            date_lbl.setStyleSheet(
                f"color: {COLORS['text_muted']}; font-size: 10px; border: none;"
            )
            layout.addWidget(date_lbl)

        # Duration pill
        dur_lbl = QLabel(_fmt_duration(clip.duration_s))
        dur_lbl.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 10px; "
            f"font-family: 'SF Mono', 'Menlo', monospace; "
            f"background: rgba(255,255,255,0.04); border-radius: 8px; "
            f"padding: 2px 8px; border: none;"
        )
        layout.addWidget(dur_lbl)

        # Analysis results
        if clip.analyzed:
            offset_lbl = QLabel(_fmt_offset(clip.timeline_offset_s))
            offset_lbl.setStyleSheet(
                f"color: {COLORS['text_dim']}; font-size: 10px; "
                f"font-family: 'SF Mono', 'Menlo', monospace; border: none;"
            )
            layout.addWidget(offset_lbl)

            # Confidence circle
            conf = clip.confidence
            if conf < 3.0:
                conf_color = COLORS["warning"]
            elif conf < 8.0:
                conf_color = COLORS["text_dim"]
            else:
                conf_color = COLORS["success"]

            conf_lbl = QLabel(f"{conf:.1f}")
            conf_lbl.setFixedSize(32, 22)
            conf_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            conf_lbl.setStyleSheet(
                f"color: {conf_color}; font-size: 10px; font-weight: 600; "
                f"font-family: 'SF Mono', 'Menlo', monospace; "
                f"background: {conf_color}15; border-radius: 11px; border: none;"
            )
            layout.addWidget(conf_lbl)

        self.setToolTip(clip.file_path)

    def _show_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        act = menu.addAction("Remove File")
        act.triggered.connect(lambda: self.removed.emit(self._index))
        menu.exec(self.mapToGlobal(pos))


# ---------------------------------------------------------------------------
#  TrackCard — glassmorphism media-folder card
# ---------------------------------------------------------------------------

class TrackCard(QFrame):
    """A track rendered as a frosted-glass media folder card."""

    files_requested = pyqtSignal(int)
    remove_requested = pyqtSignal(int)
    rename_requested = pyqtSignal(int)
    reference_requested = pyqtSignal(int)
    clip_removed = pyqtSignal(int, int)
    selected = pyqtSignal(int)
    files_dropped = pyqtSignal(int, list)

    def __init__(
        self, track: Track, index: int, parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._track = track
        self._index = index
        self._expanded = True
        self._selected = False
        self.setObjectName("TrackCard")
        self.setAcceptDrops(True)

        self._build_ui()

    def _build_ui(self) -> None:
        color = track_color(self._index)
        track = self._track

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # --- Header (folder tab) ---
        header = QFrame()
        header.setObjectName("TrackCardHeader")
        header.setCursor(QCursor(Qt.CursorShape.PointingHandCursor))
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(16, 14, 14, 10)
        header_layout.setSpacing(12)

        # Circular color indicator
        dot = QWidget()
        dot.setFixedSize(12, 12)
        dot.setStyleSheet(
            f"background: {color}; border-radius: 6px; border: none;"
        )
        header_layout.addWidget(dot)

        # Folder icon + track name
        folder_icon = QLabel("\U0001F4C1")
        folder_icon.setStyleSheet(f"font-size: 15px; border: none; color: {color};")
        header_layout.addWidget(folder_icon)

        name_lbl = QLabel(track.name)
        name_lbl.setStyleSheet(
            f"color: {COLORS['text_bright']}; font-size: 14px; "
            f"font-weight: 600; letter-spacing: -0.2px; border: none;"
        )
        header_layout.addWidget(name_lbl)

        # REF badge
        if track.is_reference:
            ref_badge = QLabel("REF")
            ref_badge.setFixedHeight(22)
            ref_badge.setStyleSheet(
                f"background: {COLORS['accent_subtle']}; color: {COLORS['accent']}; "
                f"border-radius: 11px; padding: 2px 10px; "
                f"font-size: 10px; font-weight: 700; letter-spacing: 0.5px; border: none;"
            )
            header_layout.addWidget(ref_badge)

        header_layout.addStretch()

        # File count + duration pill
        count = track.clip_count
        if count > 0:
            dur = track.total_duration_s
            info_parts = [f"{count} file{'s' if count != 1 else ''}"]
            info_parts.append(_fmt_duration(dur))
            time_span = _get_track_time_span(track)
            if time_span:
                info_parts.append(time_span)
            info_text = " \u00b7 ".join(info_parts)
        else:
            info_text = "Empty"

        info_lbl = QLabel(info_text)
        info_lbl.setStyleSheet(
            f"color: {COLORS['text_dim']}; font-size: 11px; "
            f"font-family: 'SF Mono', 'Menlo', monospace; border: none;"
        )
        header_layout.addWidget(info_lbl)

        # Add files button — pill
        add_btn = QPushButton("+ Add")
        add_btn.setFixedHeight(28)
        add_btn.setStyleSheet(
            f"QPushButton {{ background: rgba(255,255,255,0.05); color: {COLORS['text']}; "
            f"border: 1px solid {COLORS['border_light']}; border-radius: 14px; "
            f"padding: 0 14px; font-size: 11px; font-weight: 500; }}"
            f"QPushButton:hover {{ background: {COLORS['bg_hover']}; "
            f"border-color: {COLORS['accent']}; color: {COLORS['text_bright']}; }}"
        )
        add_btn.clicked.connect(lambda: self.files_requested.emit(self._index))
        header_layout.addWidget(add_btn)

        # Menu button — circular
        menu_btn = QPushButton("\u22EF")
        menu_btn.setFixedSize(28, 28)
        menu_btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {COLORS['text_dim']}; "
            f"border: none; border-radius: 14px; font-size: 16px; }}"
            f"QPushButton:hover {{ background: rgba(255,255,255,0.06); "
            f"color: {COLORS['text_bright']}; }}"
        )
        menu_btn.clicked.connect(self._show_menu)
        header_layout.addWidget(menu_btn)

        main_layout.addWidget(header)

        # --- Separator line ---
        if track.clips:
            sep = QFrame()
            sep.setFixedHeight(1)
            sep.setStyleSheet(
                f"background: {COLORS['border_subtle']}; "
                f"border: none; margin: 0 16px;"
            )
            main_layout.addWidget(sep)

        # --- Clip list ---
        self._clip_container = QWidget()
        self._clip_container.setObjectName("ClipContainer")
        clip_layout = QVBoxLayout(self._clip_container)
        clip_layout.setContentsMargins(6, 4, 6, 8)
        clip_layout.setSpacing(2)

        if not track.clips:
            empty_lbl = QLabel("Drop files here or click + Add")
            empty_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            empty_lbl.setStyleSheet(
                f"color: {COLORS['text_muted']}; font-size: 11px; "
                f"font-style: italic; padding: 16px; border: none;"
            )
            clip_layout.addWidget(empty_lbl)
        else:
            for i, clip in enumerate(track.clips):
                row = ClipRow(clip, i, color)
                row.removed.connect(lambda ci: self.clip_removed.emit(self._index, ci))
                clip_layout.addWidget(row)

        main_layout.addWidget(self._clip_container)
        self._apply_style()

    def _apply_style(self) -> None:
        color = track_color(self._index)
        if self._selected:
            border = f"rgba(56, 189, 248, 0.30)"
            bg = "rgba(21, 28, 46, 0.80)"
        else:
            border = COLORS["border_subtle"]
            bg = "rgba(21, 28, 46, 0.55)"

        self.setStyleSheet(
            f"QFrame#TrackCard {{ "
            f"background: {bg}; "
            f"border: 1px solid {border}; "
            f"border-top: 3px solid {color}; "
            f"border-radius: 16px; "
            f"}}"
            f"QFrame#TrackCardHeader {{ background: transparent; border: none; border-radius: 0; }}"
            f"QFrame#ClipRow {{ "
            f"background: transparent; border: none; border-radius: 10px; "
            f"}}"
            f"QFrame#ClipRow:hover {{ background: rgba(255, 255, 255, 0.04); }}"
            f"QWidget#ClipContainer {{ background: transparent; border: none; border-radius: 0; }}"
        )

    def set_selected(self, selected: bool) -> None:
        self._selected = selected
        self._apply_style()

    def _show_menu(self) -> None:
        menu = QMenu(self)
        menu.addAction("Add Files...", lambda: self.files_requested.emit(self._index))
        menu.addAction("Rename Track", lambda: self.rename_requested.emit(self._index))
        ref_act = menu.addAction("Set as Reference", lambda: self.reference_requested.emit(self._index))
        ref_act.setEnabled(not self._track.is_reference)
        menu.addSeparator()
        menu.addAction("Remove Track", lambda: self.remove_requested.emit(self._index))
        menu.exec(QCursor.pos())

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.selected.emit(self._index)
        super().mousePressEvent(event)

    # --- Drag-and-drop ---
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self._apply_style()

    def dropEvent(self, event: QDropEvent) -> None:
        self._apply_style()
        if not event.mimeData().hasUrls():
            return
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and is_supported_file(path):
                paths.append(path)
        if paths:
            event.acceptProposedAction()
            self.files_dropped.emit(self._index, paths)


# ---------------------------------------------------------------------------
#  AddZone — dashed drop target
# ---------------------------------------------------------------------------

class _AddZone(QFrame):
    """Drop zone / add track button at the bottom."""

    add_track_clicked = pyqtSignal()
    files_dropped = pyqtSignal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFixedHeight(56)
        self.setObjectName("AddZone")
        self._hovering = False

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        btn = QPushButton("+ Add Track")
        btn.setStyleSheet(
            f"QPushButton {{ background: transparent; color: {COLORS['text_muted']}; "
            f"border: none; font-size: 12px; font-weight: 500; }}"
            f"QPushButton:hover {{ color: {COLORS['accent']}; }}"
        )
        btn.clicked.connect(self.add_track_clicked.emit)
        layout.addWidget(btn, alignment=Qt.AlignmentFlag.AlignCenter)

        self._update_style()

    def _update_style(self) -> None:
        if self._hovering:
            border_color = COLORS["accent"]
            bg = "rgba(56, 189, 248, 0.05)"
        else:
            border_color = COLORS["border"]
            bg = "transparent"
        self.setStyleSheet(
            f"QFrame#AddZone {{ "
            f"background: {bg}; "
            f"border: 1px dashed {border_color}; "
            f"border-radius: 16px; "
            f"}}"
        )

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            self._hovering = True
            self._update_style()

    def dragLeaveEvent(self, event) -> None:
        self._hovering = False
        self._update_style()

    def dropEvent(self, event: QDropEvent) -> None:
        self._hovering = False
        self._update_style()
        if not event.mimeData().hasUrls():
            return
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and is_supported_file(path):
                paths.append(path)
        if paths:
            event.acceptProposedAction()
            self.files_dropped.emit(paths)


# ---------------------------------------------------------------------------
#  TrackPanel — scrollable list of media-folder cards
# ---------------------------------------------------------------------------

class TrackPanel(QWidget):
    """Card-based track list with the same public API as the original."""

    tracks_changed = pyqtSignal()
    reference_changed = pyqtSignal(int)
    files_requested = pyqtSignal(int)
    files_dropped_on_empty = pyqtSignal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._tracks: list[Track] = []
        self._selected_index: int = -1
        self._cards: list[TrackCard] = []
        self._pending_drop_paths: Optional[list[str]] = None

        self._build_ui()
        self.setAcceptDrops(True)

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        # Header label
        header = QLabel("  TRACKS")
        header.setFixedHeight(28)
        header.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: 10px; font-weight: 600; "
            f"letter-spacing: 1.5px; padding: 6px 12px 2px; background: transparent;"
        )
        outer.addWidget(header)

        # Scroll area
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._scroll.setStyleSheet("QScrollArea { background: transparent; border: none; }")

        self._content = QWidget()
        self._content.setStyleSheet("background: transparent;")
        self._layout = QVBoxLayout(self._content)
        self._layout.setContentsMargins(12, 4, 12, 8)
        self._layout.setSpacing(10)
        self._layout.addStretch()

        # Add zone
        self._add_zone = _AddZone()
        self._add_zone.add_track_clicked.connect(lambda: self.add_track())
        self._add_zone.files_dropped.connect(self.files_dropped_on_empty.emit)
        self._layout.addWidget(self._add_zone)

        self._scroll.setWidget(self._content)
        outer.addWidget(self._scroll)

    # ----- Public API --------------------------------------------------------

    @property
    def tracks(self) -> list[Track]:
        return self._tracks

    @tracks.setter
    def tracks(self, value: list[Track]) -> None:
        self._tracks = value
        self._rebuild()

    def add_track(self, name: Optional[str] = None) -> int:
        if name is None:
            name = f"Track {len(self._tracks) + 1}"
        track = Track(name=name)
        self._tracks.append(track)
        self._rebuild()
        self.tracks_changed.emit()
        return len(self._tracks) - 1

    def add_clips_to_track(self, track_index: int, clips: list[Clip]) -> None:
        if 0 <= track_index < len(self._tracks):
            self._tracks[track_index].clips.extend(clips)
            self._tracks[track_index].sort_clips_by_time()
            self._rebuild()
            self.tracks_changed.emit()

    def remove_selected(self) -> None:
        if self._selected_index < 0 or self._selected_index >= len(self._tracks):
            return
        del self._tracks[self._selected_index]
        self._selected_index = -1
        self._rebuild()
        self.tracks_changed.emit()

    def set_reference(self, track_index: int) -> None:
        for i, t in enumerate(self._tracks):
            t.is_reference = (i == track_index)
        self._rebuild()
        self.reference_changed.emit(track_index)

    def selected_track_index(self) -> int:
        return self._selected_index

    def refresh(self) -> None:
        self._rebuild()

    def clear_all(self) -> None:
        """Remove all tracks and clips."""
        self._tracks.clear()
        self._selected_index = -1
        self._rebuild()
        self.tracks_changed.emit()

    def reset_analysis(self) -> None:
        for track in self._tracks:
            track.synced_audio = None
            for clip in track.clips:
                clip.timeline_offset_samples = 0
                clip.timeline_offset_s = 0.0
                clip.confidence = 0.0
                clip.analyzed = False
        self._rebuild()

    # ----- Internal ----------------------------------------------------------

    def _rebuild(self) -> None:
        for card in self._cards:
            self._layout.removeWidget(card)
            card.deleteLater()
        self._cards.clear()

        for i, track in enumerate(self._tracks):
            card = TrackCard(track, i)
            card.files_requested.connect(self.files_requested.emit)
            card.remove_requested.connect(self._on_remove_track)
            card.rename_requested.connect(self._on_rename_track)
            card.reference_requested.connect(self.set_reference)
            card.clip_removed.connect(self._on_remove_clip)
            card.selected.connect(self._on_card_selected)
            card.files_dropped.connect(self._on_card_files_dropped)

            if i == self._selected_index:
                card.set_selected(True)

            self._layout.insertWidget(len(self._cards), card)
            self._cards.append(card)

    def _on_card_selected(self, index: int) -> None:
        self._selected_index = index
        for i, card in enumerate(self._cards):
            card.set_selected(i == index)

    def _on_remove_track(self, index: int) -> None:
        if 0 <= index < len(self._tracks):
            del self._tracks[index]
            if self._selected_index == index:
                self._selected_index = -1
            elif self._selected_index > index:
                self._selected_index -= 1
            self._rebuild()
            self.tracks_changed.emit()

    def _on_rename_track(self, index: int) -> None:
        if 0 <= index < len(self._tracks):
            track = self._tracks[index]
            name, ok = QInputDialog.getText(
                self, "Rename Track", "Track name:", text=track.name
            )
            if ok and name.strip():
                track.name = name.strip()
                self._rebuild()
                self.tracks_changed.emit()

    def _on_remove_clip(self, track_index: int, clip_index: int) -> None:
        if 0 <= track_index < len(self._tracks):
            track = self._tracks[track_index]
            if 0 <= clip_index < len(track.clips):
                del track.clips[clip_index]
                self._rebuild()
                self.tracks_changed.emit()

    def _on_card_files_dropped(self, track_index: int, paths: list[str]) -> None:
        self._pending_drop_paths = paths
        self.files_requested.emit(track_index)

    # --- Drag-and-drop on the panel itself ---
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        if not event.mimeData().hasUrls():
            return
        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and is_supported_file(path):
                paths.append(path)
        if paths:
            event.acceptProposedAction()
            self.files_dropped_on_empty.emit(paths)
