"""Dark pro-audio theme for AudioSync Pro."""

from __future__ import annotations

# ---------------------------------------------------------------------------
#  Color Palette
# ---------------------------------------------------------------------------

COLORS = {
    "bg_dark":        "#1a1a1a",
    "bg_panel":       "#242424",
    "bg_input":       "#2e2e2e",
    "bg_hover":       "#363636",
    "bg_selected":    "#0d3b3b",
    "border":         "#3a3a3a",
    "border_light":   "#4a4a4a",
    "text":           "#e0e0e0",
    "text_dim":       "#888888",
    "text_bright":    "#ffffff",
    "accent":         "#00bfa5",
    "accent_hover":   "#00d9bb",
    "accent_pressed": "#009688",
    "danger":         "#e74c3c",
    "danger_hover":   "#ff6b5a",
    "warning":        "#f39c12",
    "success":        "#27ae60",
    "track_colors": [
        "#00bfa5",  # teal
        "#5c6bc0",  # indigo
        "#ef5350",  # red
        "#ff9800",  # orange
        "#66bb6a",  # green
        "#ab47bc",  # purple
        "#42a5f5",  # blue
        "#ffa726",  # amber
    ],
}


# ---------------------------------------------------------------------------
#  QSS Stylesheet
# ---------------------------------------------------------------------------

STYLESHEET = f"""
/* ===== Global ===== */
QWidget {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text']};
    font-family: "SF Pro Text", "Segoe UI", "Helvetica Neue", Arial;
    font-size: 13px;
    selection-background-color: {COLORS['accent']};
    selection-color: {COLORS['text_bright']};
}}

/* ===== Main Window ===== */
QMainWindow {{
    background-color: {COLORS['bg_dark']};
}}

QMainWindow::separator {{
    background-color: {COLORS['border']};
    width: 1px;
    height: 1px;
}}

/* ===== Menu Bar ===== */
QMenuBar {{
    background-color: {COLORS['bg_panel']};
    border-bottom: 1px solid {COLORS['border']};
    padding: 2px 0;
}}

QMenuBar::item {{
    padding: 4px 12px;
    border-radius: 3px;
}}

QMenuBar::item:selected {{
    background-color: {COLORS['bg_hover']};
}}

QMenu {{
    background-color: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 4px 0;
}}

QMenu::item {{
    padding: 6px 28px 6px 12px;
}}

QMenu::item:selected {{
    background-color: {COLORS['bg_selected']};
}}

QMenu::separator {{
    height: 1px;
    background: {COLORS['border']};
    margin: 4px 8px;
}}

/* ===== Toolbar ===== */
QToolBar {{
    background-color: {COLORS['bg_panel']};
    border-bottom: 1px solid {COLORS['border']};
    padding: 4px 8px;
    spacing: 6px;
}}

QToolBar::separator {{
    width: 1px;
    background: {COLORS['border']};
    margin: 4px 6px;
}}

/* ===== Buttons ===== */
QPushButton {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 6px 16px;
    font-weight: 500;
    min-height: 20px;
}}

QPushButton:hover {{
    background-color: {COLORS['bg_hover']};
    border-color: {COLORS['border_light']};
}}

QPushButton:pressed {{
    background-color: {COLORS['bg_dark']};
}}

QPushButton:disabled {{
    color: {COLORS['text_dim']};
    background-color: {COLORS['bg_dark']};
    border-color: {COLORS['border']};
}}

/* Accent buttons (Analyze, Sync) */
QPushButton[cssClass="accent"] {{
    background-color: {COLORS['accent']};
    color: {COLORS['bg_dark']};
    border: none;
    font-weight: 600;
}}

QPushButton[cssClass="accent"]:hover {{
    background-color: {COLORS['accent_hover']};
}}

QPushButton[cssClass="accent"]:pressed {{
    background-color: {COLORS['accent_pressed']};
}}

QPushButton[cssClass="accent"]:disabled {{
    background-color: {COLORS['border']};
    color: {COLORS['text_dim']};
}}

/* Danger buttons (Reset, Remove) */
QPushButton[cssClass="danger"] {{
    background-color: transparent;
    color: {COLORS['danger']};
    border: 1px solid {COLORS['danger']};
}}

QPushButton[cssClass="danger"]:hover {{
    background-color: {COLORS['danger']};
    color: {COLORS['text_bright']};
}}

/* ===== Tree Widget ===== */
QTreeWidget {{
    background-color: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    outline: none;
    padding: 4px;
}}

QTreeWidget::item {{
    padding: 4px 8px;
    border-radius: 3px;
    min-height: 22px;
}}

QTreeWidget::item:hover {{
    background-color: {COLORS['bg_hover']};
}}

QTreeWidget::item:selected {{
    background-color: {COLORS['bg_selected']};
    color: {COLORS['text_bright']};
}}

QTreeWidget::branch {{
    background-color: transparent;
}}

QHeaderView::section {{
    background-color: {COLORS['bg_panel']};
    color: {COLORS['text_dim']};
    border: none;
    border-bottom: 1px solid {COLORS['border']};
    padding: 4px 8px;
    font-size: 11px;
    text-transform: uppercase;
}}

/* ===== Scroll Bar ===== */
QScrollBar:vertical {{
    background-color: {COLORS['bg_dark']};
    width: 8px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS['border_light']};
    border-radius: 4px;
    min-height: 30px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS['text_dim']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}

QScrollBar:horizontal {{
    background-color: {COLORS['bg_dark']};
    height: 8px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLORS['border_light']};
    border-radius: 4px;
    min-width: 30px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {COLORS['text_dim']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ===== Splitter ===== */
QSplitter::handle {{
    background-color: {COLORS['border']};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

/* ===== Status Bar ===== */
QStatusBar {{
    background-color: {COLORS['bg_panel']};
    border-top: 1px solid {COLORS['border']};
    color: {COLORS['text_dim']};
    font-size: 12px;
    padding: 2px 8px;
}}

/* ===== Combo Box ===== */
QComboBox {{
    background-color: {COLORS['bg_input']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 4px 8px;
    min-height: 20px;
}}

QComboBox:hover {{
    border-color: {COLORS['border_light']};
}}

QComboBox::drop-down {{
    border: none;
    width: 20px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_panel']};
    border: 1px solid {COLORS['border']};
    selection-background-color: {COLORS['bg_selected']};
}}

/* ===== Spin Box ===== */
QSpinBox {{
    background-color: {COLORS['bg_input']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    padding: 4px 8px;
}}

/* ===== Labels ===== */
QLabel {{
    background-color: transparent;
    color: {COLORS['text']};
}}

QLabel[cssClass="heading"] {{
    font-size: 14px;
    font-weight: 600;
    color: {COLORS['text_bright']};
}}

QLabel[cssClass="dim"] {{
    color: {COLORS['text_dim']};
    font-size: 11px;
}}

/* ===== Progress Bar ===== */
QProgressBar {{
    background-color: {COLORS['bg_input']};
    border: 1px solid {COLORS['border']};
    border-radius: 4px;
    text-align: center;
    color: {COLORS['text']};
    height: 16px;
}}

QProgressBar::chunk {{
    background-color: {COLORS['accent']};
    border-radius: 3px;
}}

/* ===== Dialog ===== */
QDialog {{
    background-color: {COLORS['bg_dark']};
}}

/* ===== Group Box ===== */
QGroupBox {{
    border: 1px solid {COLORS['border']};
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: 600;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
    color: {COLORS['text']};
}}

/* ===== Tool Tips ===== */
QToolTip {{
    background-color: {COLORS['bg_panel']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 3px;
    padding: 4px 8px;
}}
"""


def track_color(index: int) -> str:
    """Return a track color by index (cycles through palette)."""
    colors = COLORS["track_colors"]
    return colors[index % len(colors)]
