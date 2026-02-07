"""AudioSync Pro — Dark Navy + Electric Blue theme (icon-inspired)."""

from __future__ import annotations

# ---------------------------------------------------------------------------
#  Color Palette — Dark Navy with Cyan / Purple accents
#  Inspired by the icon: deep navy background with luminous blue waveforms
# ---------------------------------------------------------------------------

COLORS = {
    # Backgrounds — deep navy, layered glass
    "bg_dark":          "#0a0e1a",
    "bg_panel":         "rgba(255, 255, 255, 0.04)",
    "bg_panel_solid":   "#111827",
    "bg_input":         "rgba(255, 255, 255, 0.06)",
    "bg_hover":         "rgba(56, 189, 248, 0.10)",
    "bg_selected":      "rgba(56, 189, 248, 0.18)",

    # Borders — subtle blue-tinted glass edges
    "border":           "rgba(56, 189, 248, 0.08)",
    "border_light":     "rgba(56, 189, 248, 0.18)",

    # Text — bright on dark navy
    "text":             "#e0e7ff",
    "text_dim":         "rgba(224, 231, 255, 0.60)",
    "text_bright":      "#f0f4ff",
    "text_tertiary":    "rgba(224, 231, 255, 0.35)",

    # Accent — cyan-blue primary, purple secondary
    "accent":           "#38bdf8",
    "accent_hover":     "#7dd3fc",
    "accent_pressed":   "#0ea5e9",
    "accent_subtle":    "rgba(56, 189, 248, 0.15)",
    "secondary":        "#a78bfa",
    "secondary_hover":  "#c4b5fd",

    # Status colors
    "danger":           "#f87171",
    "danger_hover":     "#fca5a5",
    "warning":          "#fbbf24",
    "success":          "#34d399",

    # Track palette — vivid, cool-toned
    "track_colors": [
        "#38bdf8",   # Cyan
        "#a78bfa",   # Violet
        "#2dd4bf",   # Teal
        "#fb7185",   # Rose
        "#fbbf24",   # Amber
        "#818cf8",   # Indigo
        "#34d399",   # Emerald
        "#e879f9",   # Fuchsia
    ],
}


# ---------------------------------------------------------------------------
#  QSS Stylesheet — Navy Glass
# ---------------------------------------------------------------------------

STYLESHEET = f"""
/* ===== Global ===== */
QWidget {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text']};
    font-family: "SF Pro Display", "SF Pro Text", ".AppleSystemUIFont",
                 "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    font-size: 13px;
    selection-background-color: {COLORS['accent']};
    selection-color: {COLORS['text_bright']};
}}

QMainWindow {{
    background-color: {COLORS['bg_dark']};
}}

/* ===== Menu Bar — glass panel ===== */
QMenuBar {{
    background-color: {COLORS['bg_panel_solid']};
    color: {COLORS['text']};
    border-bottom: 1px solid {COLORS['border']};
    padding: 3px 0;
    font-size: 12px;
}}

QMenuBar::item {{
    color: {COLORS['text']};
    padding: 5px 14px;
    border-radius: 8px;
    margin: 1px 2px;
}}

QMenuBar::item:selected {{
    background-color: {COLORS['bg_hover']};
    color: {COLORS['text_bright']};
}}

QMenu {{
    background-color: {COLORS['bg_panel_solid']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 12px;
    padding: 6px 0;
}}

QMenu::item {{
    color: {COLORS['text']};
    padding: 7px 32px 7px 16px;
    border-radius: 6px;
    margin: 0 4px;
}}

QMenu::item:selected {{
    background-color: {COLORS['bg_hover']};
    color: {COLORS['text_bright']};
}}

QMenu::item:disabled {{
    color: {COLORS['text_tertiary']};
}}

QMenu::separator {{
    height: 1px;
    background: {COLORS['border']};
    margin: 6px 12px;
}}

/* ===== Toolbar — glass bar ===== */
QToolBar {{
    background-color: {COLORS['bg_panel_solid']};
    border-bottom: 1px solid {COLORS['border']};
    padding: 6px 12px;
    spacing: 8px;
}}

QToolBar::separator {{
    width: 1px;
    background: {COLORS['border']};
    margin: 6px 4px;
}}

/* ===== Buttons — glass pill style ===== */
QPushButton {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 12px;
    padding: 7px 18px;
    font-weight: 500;
    font-size: 12px;
    min-height: 18px;
}}

QPushButton:hover {{
    background-color: {COLORS['bg_hover']};
    border-color: {COLORS['accent']};
    color: {COLORS['text_bright']};
}}

QPushButton:pressed {{
    background-color: rgba(56, 189, 248, 0.06);
}}

QPushButton:disabled {{
    color: {COLORS['text_tertiary']};
    background-color: {COLORS['bg_dark']};
    border-color: {COLORS['border']};
}}

/* Accent buttons — solid cyan pill */
QPushButton[cssClass="accent"] {{
    background-color: {COLORS['accent']};
    color: #0a0e1a;
    border: none;
    font-weight: 600;
    border-radius: 12px;
    padding: 7px 22px;
}}

QPushButton[cssClass="accent"]:hover {{
    background-color: {COLORS['accent_hover']};
}}

QPushButton[cssClass="accent"]:pressed {{
    background-color: {COLORS['accent_pressed']};
}}

QPushButton[cssClass="accent"]:disabled {{
    background-color: {COLORS['border']};
    color: {COLORS['text_tertiary']};
}}

/* Primary action button — larger, solid accent */
QPushButton[cssClass="primary"] {{
    background-color: {COLORS['accent']};
    color: #0a0e1a;
    border: none;
    font-weight: 700;
    font-size: 13px;
    border-radius: 14px;
    padding: 8px 28px;
    min-height: 22px;
}}

QPushButton[cssClass="primary"]:hover {{
    background-color: {COLORS['accent_hover']};
}}

QPushButton[cssClass="primary"]:pressed {{
    background-color: {COLORS['accent_pressed']};
}}

QPushButton[cssClass="primary"]:disabled {{
    background-color: {COLORS['border']};
    color: {COLORS['text_tertiary']};
}}

/* Danger buttons — ghost style, red */
QPushButton[cssClass="danger"] {{
    background-color: transparent;
    color: {COLORS['danger']};
    border: 1px solid transparent;
    font-weight: 500;
}}

QPushButton[cssClass="danger"]:hover {{
    background-color: rgba(248, 113, 113, 0.12);
    border-color: {COLORS['danger']};
    color: {COLORS['danger_hover']};
}}

QPushButton[cssClass="danger"]:pressed {{
    background-color: rgba(248, 113, 113, 0.2);
}}

/* ===== Tree Widget — glass panel ===== */
QTreeWidget {{
    background-color: {COLORS['bg_panel_solid']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 14px;
    outline: none;
    padding: 6px;
}}

QTreeWidget::item {{
    color: {COLORS['text']};
    padding: 5px 8px;
    border-radius: 8px;
    min-height: 24px;
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
    background-color: {COLORS['bg_panel_solid']};
    color: {COLORS['text_dim']};
    border: none;
    border-bottom: 1px solid {COLORS['border']};
    padding: 6px 10px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.5px;
    text-transform: uppercase;
}}

/* ===== Table Widget — glass panel ===== */
QTableWidget {{
    background-color: {COLORS['bg_panel_solid']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 14px;
    gridline-color: {COLORS['border']};
    outline: none;
}}

QTableWidget::item {{
    color: {COLORS['text']};
    padding: 4px 8px;
    border-bottom: 1px solid {COLORS['border']};
}}

QTableWidget::item:selected {{
    background-color: {COLORS['bg_selected']};
    color: {COLORS['text_bright']};
}}

QTableWidgetItem {{
    color: {COLORS['text']};
}}

/* ===== Scroll Bar — ultra-thin, near-invisible ===== */
QScrollBar:vertical {{
    background-color: transparent;
    width: 5px;
    margin: 4px 1px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {COLORS['border_light']};
    border-radius: 2px;
    min-height: 40px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {COLORS['accent']};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0;
    background: transparent;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 5px;
    margin: 1px 4px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {COLORS['border_light']};
    border-radius: 2px;
    min-width: 40px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {COLORS['accent']};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    width: 0;
    background: transparent;
}}

/* ===== Splitter ===== */
QSplitter::handle {{
    background-color: {COLORS['border']};
}}

QSplitter::handle:horizontal {{
    width: 1px;
}}

/* ===== Status Bar — glass ===== */
QStatusBar {{
    background-color: {COLORS['bg_panel_solid']};
    border-top: 1px solid {COLORS['border']};
    color: {COLORS['text_dim']};
    font-size: 11px;
    padding: 4px 12px;
}}

QStatusBar QLabel {{
    color: {COLORS['text_dim']};
}}

/* ===== Combo Box — glass ===== */
QComboBox {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 12px;
    padding: 6px 12px;
    min-height: 18px;
    font-size: 12px;
}}

QComboBox:hover {{
    border-color: {COLORS['accent']};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_panel_solid']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 10px;
    selection-background-color: {COLORS['bg_hover']};
    selection-color: {COLORS['text_bright']};
    padding: 4px;
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
    letter-spacing: -0.2px;
}}

QLabel[cssClass="dim"] {{
    color: {COLORS['text_dim']};
    font-size: 11px;
}}

/* ===== Line Edit — glass input ===== */
QLineEdit {{
    background-color: {COLORS['bg_input']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 12px;
    padding: 6px 12px;
    color: {COLORS['text']};
    font-size: 12px;
}}

QLineEdit:focus {{
    border-color: {COLORS['accent']};
}}

/* ===== Progress Bar — Cyan accent ===== */
QProgressBar {{
    background-color: {COLORS['bg_input']};
    border: none;
    border-radius: 7px;
    text-align: center;
    color: {COLORS['text']};
    font-size: 11px;
    font-weight: 600;
}}

QProgressBar::chunk {{
    background-color: {COLORS['accent']};
    border-radius: 7px;
}}

/* ===== Dialog — glass ===== */
QDialog {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text']};
}}

/* ===== Message Box — ensure text is light ===== */
QMessageBox {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text']};
}}

QMessageBox QLabel {{
    color: {COLORS['text']};
}}

/* ===== Input Dialog ===== */
QInputDialog {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text']};
}}

QInputDialog QLabel {{
    color: {COLORS['text']};
}}

QInputDialog QLineEdit {{
    color: {COLORS['text']};
}}

/* ===== Dialog Button Box ===== */
QDialogButtonBox QPushButton {{
    color: {COLORS['text']};
}}

/* ===== Group Box — glass card ===== */
QGroupBox {{
    border: 1px solid {COLORS['border_light']};
    border-radius: 14px;
    margin-top: 14px;
    padding: 16px 12px 12px;
    font-weight: 600;
    font-size: 12px;
    color: {COLORS['text']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: {COLORS['text_bright']};
}}

/* ===== Tool Tips — glass ===== */
QToolTip {{
    background-color: {COLORS['bg_panel_solid']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 10px;
    padding: 6px 10px;
    font-size: 11px;
}}

/* ===== Workflow Bar — glass panel ===== */
QWidget[cssClass="workflow-bar"] {{
    background-color: {COLORS['bg_panel_solid']};
    border-bottom: 1px solid {COLORS['border']};
}}

/* ===== Form Layout Labels ===== */
QFormLayout QLabel {{
    color: {COLORS['text']};
}}
"""


def track_color(index: int) -> str:
    """Return a track color by index (cycles through palette)."""
    colors = COLORS["track_colors"]
    return colors[index % len(colors)]
