"""Track panel — tree widget for managing tracks and their clips."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QColor, QFont, QPainter, QPen, QDragMoveEvent, QDropEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QInputDialog,
    QMenu,
    QTreeWidget,
    QTreeWidgetItem,
    QWidget,
)

from core.audio_io import AUDIO_EXTENSIONS, VIDEO_EXTENSIONS, is_supported_file
from core.models import Clip, Track

from .theme import COLORS, track_color


# ---------------------------------------------------------------------------
#  Constants
# ---------------------------------------------------------------------------

_FILE_FILTER = (
    "Audio/Video Files ("
    + " ".join(f"*{ext}" for ext in sorted(AUDIO_EXTENSIONS | VIDEO_EXTENSIONS))
    + ");;All Files (*)"
)

COL_NAME = 0
COL_DURATION = 1
COL_OFFSET = 2
COL_CONFIDENCE = 3

COLUMN_LABELS = ["Name", "Duration", "Offset", "Confidence"]


# ---------------------------------------------------------------------------
#  TrackPanel
# ---------------------------------------------------------------------------

class TrackPanel(QTreeWidget):
    """
    Two-level tree:
      - Level 0: Track  (device label, file count + time span, [REF] badge)
      - Level 1: Clip   (filename with [V]/[A] badge + creation date, duration, offset, confidence)

    Preserves expansion state across rebuilds using track names as keys.
    Provides visual drag-and-drop hover feedback.
    """

    tracks_changed = pyqtSignal()
    reference_changed = pyqtSignal(int)
    files_requested = pyqtSignal(int)

    # Emitted when files are dropped on empty space (no track under cursor).
    # Signal carries the list of file paths for auto-grouping.
    files_dropped_on_empty = pyqtSignal(list)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._tracks: list[Track] = []
        self._collapsed_tracks: set[str] = set()   # Track names that are collapsed

        # Drag-and-drop hover tracking
        self._drop_hover_item: Optional[QTreeWidgetItem] = None
        self._drop_hover_empty: bool = False  # True when hovering over empty space

        # Column setup
        self.setColumnCount(len(COLUMN_LABELS))
        self.setHeaderLabels(COLUMN_LABELS)
        header = self.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(COL_DURATION, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_OFFSET, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(COL_CONFIDENCE, QHeaderView.ResizeMode.ResizeToContents)

        # Behaviour
        self.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.setRootIsDecorated(True)
        self.setExpandsOnDoubleClick(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)

        # Mono font for numbers — use guaranteed system fonts
        mono = QFont("Menlo", 11)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self._mono_font = mono

    # ----- public API -------------------------------------------------------

    @property
    def tracks(self) -> list[Track]:
        return self._tracks

    @tracks.setter
    def tracks(self, value: list[Track]) -> None:
        self._tracks = value
        self._rebuild_tree()

    def add_track(self, name: Optional[str] = None) -> int:
        if name is None:
            name = f"Track {len(self._tracks) + 1}"
        track = Track(name=name)
        self._tracks.append(track)
        self._rebuild_tree()
        self.tracks_changed.emit()
        return len(self._tracks) - 1

    def add_clips_to_track(self, track_index: int, clips: list[Clip]) -> None:
        if 0 <= track_index < len(self._tracks):
            self._tracks[track_index].clips.extend(clips)
            # Auto-sort clips by creation time after adding
            self._tracks[track_index].sort_clips_by_time()
            self._rebuild_tree()
            self.tracks_changed.emit()

    def remove_selected(self) -> None:
        items = self.selectedItems()
        if not items:
            return

        tracks_to_remove: set[int] = set()
        clips_to_remove: dict[int, set[int]] = {}

        for item in items:
            parent = item.parent()
            if parent is None:
                track_idx = self.indexOfTopLevelItem(item)
                tracks_to_remove.add(track_idx)
            else:
                track_idx = self.indexOfTopLevelItem(parent)
                clip_idx = parent.indexOfChild(item)
                clips_to_remove.setdefault(track_idx, set()).add(clip_idx)

        for t_idx, c_indices in clips_to_remove.items():
            if t_idx not in tracks_to_remove:
                self._tracks[t_idx].clips = [
                    c for i, c in enumerate(self._tracks[t_idx].clips)
                    if i not in c_indices
                ]

        for t_idx in sorted(tracks_to_remove, reverse=True):
            if 0 <= t_idx < len(self._tracks):
                name = self._tracks[t_idx].name
                self._collapsed_tracks.discard(name)
                del self._tracks[t_idx]

        self._rebuild_tree()
        self.tracks_changed.emit()

    def set_reference(self, track_index: int) -> None:
        for i, t in enumerate(self._tracks):
            t.is_reference = (i == track_index)
        self._rebuild_tree()
        self.reference_changed.emit(track_index)

    def selected_track_index(self) -> int:
        items = self.selectedItems()
        if not items:
            return -1
        item = items[0]
        if item.parent() is not None:
            item = item.parent()
        return self.indexOfTopLevelItem(item)

    def refresh(self) -> None:
        self._rebuild_tree()

    def reset_analysis(self) -> None:
        for track in self._tracks:
            track.synced_audio = None
            for clip in track.clips:
                clip.timeline_offset_samples = 0
                clip.timeline_offset_s = 0.0
                clip.confidence = 0.0
                clip.analyzed = False
        self._rebuild_tree()

    # ----- tree building (preserves expansion state) -------------------------

    def _save_expansion_state(self) -> None:
        """Record which tracks are collapsed before clearing."""
        self._collapsed_tracks.clear()
        for i in range(self.topLevelItemCount()):
            item = self.topLevelItem(i)
            if item and not item.isExpanded():
                if i < len(self._tracks):
                    self._collapsed_tracks.add(self._tracks[i].name)

    def _rebuild_tree(self) -> None:
        self._save_expansion_state()
        self.clear()

        for i, track in enumerate(self._tracks):
            t_item = QTreeWidgetItem()
            color = track_color(i)

            # Track name with optional [REF] badge
            label = track.name
            if track.is_reference:
                label += "  [REF]"
            t_item.setText(COL_NAME, label)
            t_item.setForeground(COL_NAME, QColor(color))
            font = t_item.font(COL_NAME)
            font.setBold(True)
            font.setPointSize(12)
            t_item.setFont(COL_NAME, font)

            # Duration column shows total + file count + time span subtitle
            dur = track.total_duration_s
            count = track.clip_count
            if count > 0:
                dur_text = f"{_fmt_duration(dur)}  ({count} file{'s' if count != 1 else ''})"
                # Add time span if metadata available
                time_span = _get_track_time_span(track)
                if time_span:
                    dur_text += f"  {time_span}"
            else:
                dur_text = "Empty"
            t_item.setText(COL_DURATION, dur_text)
            t_item.setFont(COL_DURATION, self._mono_font)
            t_item.setForeground(COL_DURATION, QColor(COLORS["text_dim"]))

            t_item.setToolTip(COL_NAME, f"{count} file(s), {_fmt_duration(dur)} total")

            self.addTopLevelItem(t_item)

            if not track.clips:
                # Empty-track hint
                hint = QTreeWidgetItem(t_item)
                hint.setText(COL_NAME, "  Drop files here or click + Files")
                hint.setForeground(COL_NAME, QColor(COLORS["text_dim"]))
                hint_font = hint.font(COL_NAME)
                hint_font.setItalic(True)
                hint_font.setPointSize(10)
                hint.setFont(COL_NAME, hint_font)
                hint.setFlags(Qt.ItemFlag.NoItemFlags)  # Non-selectable
            else:
                for clip in track.clips:
                    c_item = QTreeWidgetItem(t_item)

                    # Clip name with [V] or [A] badge + creation date
                    badge = "[V]" if clip.is_video else "[A]"
                    date_str = _fmt_creation_date(clip.creation_time) if clip.creation_time else ""
                    name_text = f"  {badge} {clip.name}"
                    if date_str:
                        name_text += f"  \u2022 {date_str}"
                    c_item.setText(COL_NAME, name_text)
                    c_item.setForeground(COL_NAME, QColor(COLORS["text"]))

                    c_item.setText(COL_DURATION, _fmt_duration(clip.duration_s))
                    c_item.setFont(COL_DURATION, self._mono_font)
                    c_item.setForeground(COL_DURATION, QColor(COLORS["text_dim"]))

                    if clip.analyzed:
                        c_item.setText(COL_OFFSET, _fmt_offset(clip.timeline_offset_s))
                        c_item.setFont(COL_OFFSET, self._mono_font)

                        conf_text = f"{clip.confidence:.1f}"
                        c_item.setText(COL_CONFIDENCE, conf_text)
                        c_item.setFont(COL_CONFIDENCE, self._mono_font)
                        if clip.confidence < 3.0:
                            c_item.setForeground(COL_CONFIDENCE, QColor(COLORS["warning"]))
                        elif clip.confidence < 8.0:
                            c_item.setForeground(COL_CONFIDENCE, QColor(COLORS["text_dim"]))
                        else:
                            c_item.setForeground(COL_CONFIDENCE, QColor(COLORS["success"]))

                    if clip.is_video:
                        c_item.setToolTip(COL_NAME, f"Video: {clip.file_path}")
                    else:
                        c_item.setToolTip(COL_NAME, clip.file_path)

            # Restore expansion state
            is_collapsed = track.name in self._collapsed_tracks
            t_item.setExpanded(not is_collapsed)

    # ----- context menu -----------------------------------------------------

    def _show_context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        menu = QMenu(self)

        if item is None:
            action_add = menu.addAction("Add Track")
            action_add.triggered.connect(lambda: self.add_track())
        elif item.parent() is None:
            track_idx = self.indexOfTopLevelItem(item)
            if track_idx < 0 or track_idx >= len(self._tracks):
                return
            track = self._tracks[track_idx]

            action_rename = menu.addAction("Rename Track")
            action_rename.triggered.connect(lambda: self._rename_track(track_idx))

            action_ref = menu.addAction("Set as Reference")
            action_ref.triggered.connect(lambda: self.set_reference(track_idx))
            action_ref.setEnabled(not track.is_reference)

            action_add_files = menu.addAction("Add Files...")
            action_add_files.triggered.connect(lambda: self.files_requested.emit(track_idx))

            menu.addSeparator()

            action_remove = menu.addAction("Remove Track")
            action_remove.triggered.connect(lambda: self._remove_track(track_idx))
        else:
            parent = item.parent()
            track_idx = self.indexOfTopLevelItem(parent)
            clip_idx = parent.indexOfChild(item)

            # Ignore hint items (non-selectable empty-track placeholder)
            if not (item.flags() & Qt.ItemFlag.ItemIsSelectable):
                return

            action_remove = menu.addAction("Remove File")
            action_remove.triggered.connect(
                lambda: self._remove_clip(track_idx, clip_idx)
            )

        menu.exec(self.viewport().mapToGlobal(pos))

    def _rename_track(self, index: int) -> None:
        track = self._tracks[index]
        old_name = track.name
        name, ok = QInputDialog.getText(
            self, "Rename Track", "Track name:", text=track.name
        )
        if ok and name.strip():
            new_name = name.strip()
            if old_name in self._collapsed_tracks:
                self._collapsed_tracks.discard(old_name)
                self._collapsed_tracks.add(new_name)
            track.name = new_name
            self._rebuild_tree()
            self.tracks_changed.emit()

    def _remove_track(self, index: int) -> None:
        if 0 <= index < len(self._tracks):
            name = self._tracks[index].name
            self._collapsed_tracks.discard(name)
            del self._tracks[index]
            self._rebuild_tree()
            self.tracks_changed.emit()

    def _remove_clip(self, track_index: int, clip_index: int) -> None:
        track = self._tracks[track_index]
        if 0 <= clip_index < len(track.clips):
            del track.clips[clip_index]
            self._rebuild_tree()
            self.tracks_changed.emit()

    # ----- drag-and-drop with hover feedback --------------------------------

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if not event.mimeData().hasUrls():
            return

        event.acceptProposedAction()

        item = self.itemAt(event.position().toPoint())
        old_hover = self._drop_hover_item
        old_empty = self._drop_hover_empty

        if item is not None:
            # Hovering over a track or clip
            if item.parent() is not None:
                item = item.parent()  # snap to track level
            self._drop_hover_item = item
            self._drop_hover_empty = False
        else:
            self._drop_hover_item = None
            self._drop_hover_empty = True

        if old_hover != self._drop_hover_item or old_empty != self._drop_hover_empty:
            self.viewport().update()

    def dragLeaveEvent(self, event) -> None:
        self._drop_hover_item = None
        self._drop_hover_empty = False
        self.viewport().update()

    def dropEvent(self, event: QDropEvent) -> None:
        # Reset hover state
        self._drop_hover_item = None
        self._drop_hover_empty = False
        self.viewport().update()

        if not event.mimeData().hasUrls():
            return

        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and is_supported_file(path):
                paths.append(path)

        if not paths:
            return

        event.acceptProposedAction()

        item = self.itemAt(event.position().toPoint())
        if item is not None:
            # Drop on an existing track
            if item.parent() is not None:
                item = item.parent()
            track_idx = self.indexOfTopLevelItem(item)
            self._pending_drop_paths = paths
            self._pending_drop_track = track_idx
            self.files_requested.emit(track_idx)
        else:
            # Drop on empty space -> emit for auto-grouping
            self.files_dropped_on_empty.emit(paths)

    def paintEvent(self, event) -> None:
        super().paintEvent(event)

        if self._drop_hover_item is not None or self._drop_hover_empty:
            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            if self._drop_hover_item is not None:
                # Highlight hovered track with accent border
                rect = self.visualItemRect(self._drop_hover_item)
                accent = QColor(COLORS["accent"])
                accent.setAlpha(40)
                painter.fillRect(rect, accent)
                painter.setPen(QPen(QColor(COLORS["accent"]), 2))
                painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 8, 8)
            elif self._drop_hover_empty:
                # Drop zone at the bottom
                vp = self.viewport()
                last_rect = QRect(0, 0, vp.width(), vp.height())

                # Position it below the last item
                n = self.topLevelItemCount()
                if n > 0:
                    last_item = self.topLevelItem(n - 1)
                    if last_item:
                        item_rect = self.visualItemRect(last_item)
                        y = item_rect.bottom() + 8
                    else:
                        y = 40
                else:
                    y = 40

                zone_rect = QRect(8, y, vp.width() - 16, 36)
                accent = QColor(COLORS["accent"])
                accent.setAlpha(25)
                painter.fillRect(zone_rect, accent)
                painter.setPen(QPen(QColor(COLORS["accent"]), 1, Qt.PenStyle.DashLine))
                painter.drawRoundedRect(zone_rect.adjusted(1, 1, -1, -1), 10, 10)

                # Text
                painter.setPen(QColor(COLORS["accent"]))
                font = painter.font()
                font.setPointSize(10)
                painter.setFont(font)
                painter.drawText(zone_rect, Qt.AlignmentFlag.AlignCenter,
                                 "Drop to auto-group into new tracks")

            painter.end()


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
    """Format a Unix timestamp into a concise readable date/time."""
    try:
        dt = datetime.fromtimestamp(timestamp)
        now = datetime.now()
        if dt.year == now.year:
            return dt.strftime("%b %d, %I:%M %p")
        return dt.strftime("%b %d %Y, %I:%M %p")
    except (ValueError, OSError):
        return ""


def _get_track_time_span(track: Track) -> str:
    """Get a formatted time span string for a track from metadata."""
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
