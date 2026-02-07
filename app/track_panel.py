"""Track panel — tree widget for managing tracks and their clips."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QFont, QIcon
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QFileDialog,
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
      - Level 0: Track  (device label, file count, [REF] badge)
      - Level 1: Clip   (filename, duration, offset, confidence)
    """

    # Signals
    tracks_changed = pyqtSignal()           # Track list or clips modified
    reference_changed = pyqtSignal(int)     # Reference track index changed
    files_requested = pyqtSignal(int)       # Request to add files to track at index

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._tracks: list[Track] = []

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

        # Mono font for numbers
        mono = QFont("SF Mono", 11)
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
        """Create a new empty track. Returns its index."""
        if name is None:
            name = f"Track {len(self._tracks) + 1}"
        track = Track(name=name)
        self._tracks.append(track)
        self._rebuild_tree()
        self.tracks_changed.emit()
        return len(self._tracks) - 1

    def add_clips_to_track(self, track_index: int, clips: list[Clip]) -> None:
        """Add loaded clips to an existing track."""
        if 0 <= track_index < len(self._tracks):
            self._tracks[track_index].clips.extend(clips)
            self._rebuild_tree()
            self.tracks_changed.emit()

    def remove_selected(self) -> None:
        """Remove selected tracks or clips."""
        items = self.selectedItems()
        if not items:
            return

        # Collect tracks and clips to remove
        tracks_to_remove: set[int] = set()
        clips_to_remove: dict[int, set[int]] = {}

        for item in items:
            parent = item.parent()
            if parent is None:
                # Top-level = track
                track_idx = self.indexOfTopLevelItem(item)
                tracks_to_remove.add(track_idx)
            else:
                track_idx = self.indexOfTopLevelItem(parent)
                clip_idx = parent.indexOfChild(item)
                clips_to_remove.setdefault(track_idx, set()).add(clip_idx)

        # Remove clips first (from tracks not being deleted)
        for t_idx, c_indices in clips_to_remove.items():
            if t_idx not in tracks_to_remove:
                self._tracks[t_idx].clips = [
                    c for i, c in enumerate(self._tracks[t_idx].clips)
                    if i not in c_indices
                ]

        # Remove tracks (reverse order to preserve indices)
        for t_idx in sorted(tracks_to_remove, reverse=True):
            if 0 <= t_idx < len(self._tracks):
                del self._tracks[t_idx]

        self._rebuild_tree()
        self.tracks_changed.emit()

    def set_reference(self, track_index: int) -> None:
        """Mark a track as the reference."""
        for i, t in enumerate(self._tracks):
            t.is_reference = (i == track_index)
        self._rebuild_tree()
        self.reference_changed.emit(track_index)

    def selected_track_index(self) -> int:
        """Return the index of the currently selected track, or -1."""
        items = self.selectedItems()
        if not items:
            return -1
        item = items[0]
        if item.parent() is not None:
            item = item.parent()
        return self.indexOfTopLevelItem(item)

    def refresh(self) -> None:
        """Rebuild the tree from current track data."""
        self._rebuild_tree()

    def reset_analysis(self) -> None:
        """Clear analysis results from all clips."""
        for track in self._tracks:
            track.synced_audio = None
            for clip in track.clips:
                clip.timeline_offset_samples = 0
                clip.timeline_offset_s = 0.0
                clip.confidence = 0.0
                clip.analyzed = False
        self._rebuild_tree()

    # ----- tree building ----------------------------------------------------

    def _rebuild_tree(self) -> None:
        self.clear()
        for i, track in enumerate(self._tracks):
            t_item = QTreeWidgetItem()
            color = track_color(i)

            # Track name + badge
            label = track.name
            if track.is_reference:
                label += "  [REF]"
            t_item.setText(COL_NAME, label)
            t_item.setForeground(COL_NAME, QColor(color))
            font = t_item.font(COL_NAME)
            font.setBold(True)
            font.setPointSize(12)
            t_item.setFont(COL_NAME, font)

            # Duration
            dur = track.total_duration_s
            t_item.setText(COL_DURATION, _fmt_duration(dur))
            t_item.setFont(COL_DURATION, self._mono_font)
            t_item.setForeground(COL_DURATION, QColor(COLORS["text_dim"]))

            # Clip count as tooltip
            t_item.setToolTip(COL_NAME, f"{track.clip_count} file(s), {_fmt_duration(dur)} total")

            self.addTopLevelItem(t_item)

            # Child clips
            for clip in track.clips:
                c_item = QTreeWidgetItem(t_item)
                c_item.setText(COL_NAME, f"  {clip.name}")
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

            t_item.setExpanded(True)

    # ----- context menu -----------------------------------------------------

    def _show_context_menu(self, pos) -> None:
        item = self.itemAt(pos)
        menu = QMenu(self)

        if item is None:
            action_add = menu.addAction("Add Track")
            action_add.triggered.connect(lambda: self.add_track())
        elif item.parent() is None:
            # Track-level
            track_idx = self.indexOfTopLevelItem(item)
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
            # Clip-level
            parent = item.parent()
            track_idx = self.indexOfTopLevelItem(parent)
            clip_idx = parent.indexOfChild(item)

            action_remove = menu.addAction("Remove File")
            action_remove.triggered.connect(
                lambda: self._remove_clip(track_idx, clip_idx)
            )

        menu.exec(self.viewport().mapToGlobal(pos))

    def _rename_track(self, index: int) -> None:
        track = self._tracks[index]
        name, ok = QInputDialog.getText(
            self, "Rename Track", "Track name:", text=track.name
        )
        if ok and name.strip():
            track.name = name.strip()
            self._rebuild_tree()
            self.tracks_changed.emit()

    def _remove_track(self, index: int) -> None:
        if 0 <= index < len(self._tracks):
            del self._tracks[index]
            self._rebuild_tree()
            self.tracks_changed.emit()

    def _remove_clip(self, track_index: int, clip_index: int) -> None:
        track = self._tracks[track_index]
        if 0 <= clip_index < len(track.clips):
            del track.clips[clip_index]
            self._rebuild_tree()
            self.tracks_changed.emit()

    # ----- drag-and-drop ---------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event) -> None:
        if not event.mimeData().hasUrls():
            return

        paths = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if path and is_supported_file(path):
                paths.append(path)

        if not paths:
            return

        # Drop onto a track item? Or create new track?
        item = self.itemAt(event.position().toPoint())
        if item is not None:
            if item.parent() is not None:
                item = item.parent()
            track_idx = self.indexOfTopLevelItem(item)
        else:
            track_idx = self.add_track()

        # Signal to main window to load files
        event.acceptProposedAction()
        # Store paths temporarily for the main window to process
        self._pending_drop_paths = paths
        self._pending_drop_track = track_idx
        self.files_requested.emit(track_idx)


# ---------------------------------------------------------------------------
#  Helpers
# ---------------------------------------------------------------------------

def _fmt_duration(seconds: float) -> str:
    """Format duration as M:SS or H:MM:SS."""
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
    """Format offset in seconds or milliseconds."""
    if abs(seconds) < 0.001:
        return "0 ms"
    if abs(seconds) < 1.0:
        return f"{seconds * 1000:+.1f} ms"
    return f"{seconds:+.2f} s"
