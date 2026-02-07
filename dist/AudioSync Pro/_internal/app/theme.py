"""macOS Tahoe "Liquid Glass" theme for AudioSync Pro — dark mode."""

from __future__ import annotations

# ---------------------------------------------------------------------------
#  Color Palette — Apple macOS 26 Tahoe Liquid Glass (dark mode)
# ---------------------------------------------------------------------------

COLORS = {
    # Backgrounds — deep, layered glass
    "bg_dark":          "#0d0d0f",
    "bg_panel":         "rgba(255, 255, 255, 0.05)",
    "bg_panel_solid":   "#141416",
    "bg_input":         "rgba(255, 255, 255, 0.06)",
    "bg_hover":         "rgba(255, 255, 255, 0.09)",
    "bg_selected":      "rgba(10, 132, 255, 0.20)",

    # Borders — subtle glass edges
    "border":           "rgba(255, 255, 255, 0.08)",
    "border_light":     "rgba(255, 255, 255, 0.14)",

    # Text
    "text":             "#f5f5f7",
    "text_dim":         "rgba(255, 255, 255, 0.55)",
    "text_bright":      "#ffffff",
    "text_tertiary":    "rgba(255, 255, 255, 0.35)",

    # Apple system colors
    "accent":           "#0A84FF",
    "accent_hover":     "#409CFF",
    "accent_pressed":   "#0071E3",
    "accent_subtle":    "rgba(10, 132, 255, 0.15)",
    "danger":           "#FF453A",
    "danger_hover":     "#FF6961",
    "warning":          "#FF9F0A",
    "success":          "#30D158",

    # Track palette — Apple system colors
    "track_colors": [
        "#0A84FF",   # Blue
        "#BF5AF2",   # Purple
        "#FF375F",   # Pink
        "#FF9F0A",   # Orange
        "#30D158",   # Green
        "#5E5CE6",   # Indigo
        "#64D2FF",   # Teal
        "#FFD60A",   # Yellow
    ],
}


# ---------------------------------------------------------------------------
#  QSS Stylesheet — Liquid Glass
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
    border-bottom: 1px solid {COLORS['border']};
    padding: 3px 0;
    font-size: 12px;
}}

QMenuBar::item {{
    padding: 5px 14px;
    border-radius: 8px;
    margin: 1px 2px;
}}

QMenuBar::item:selected {{
    background-color: {COLORS['bg_hover']};
}}

QMenu {{
    background-color: {COLORS['bg_panel_solid']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
    padding: 6px 0;
}}

QMenu::item {{
    padding: 7px 32px 7px 16px;
    border-radius: 6px;
    margin: 0 4px;
}}

QMenu::item:selected {{
    background-color: {COLORS['bg_hover']};
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
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
    padding: 7px 18px;
    font-weight: 500;
    font-size: 12px;
    min-height: 18px;
}}

QPushButton:hover {{
    background-color: {COLORS['bg_hover']};
    border-color: {COLORS['border_light']};
}}

QPushButton:pressed {{
    background-color: {COLORS['bg_dark']};
}}

QPushButton:disabled {{
    color: {COLORS['text_tertiary']};
    background-color: {COLORS['bg_dark']};
    border-color: {COLORS['border']};
}}

/* Accent buttons — solid Apple Blue pill */
QPushButton[cssClass="accent"] {{
    background-color: {COLORS['accent']};
    color: #ffffff;
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
    color: #ffffff;
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

/* Danger buttons — ghost style, Apple Red */
QPushButton[cssClass="danger"] {{
    background-color: transparent;
    color: {COLORS['danger']};
    border: 1px solid transparent;
    font-weight: 500;
}}

QPushButton[cssClass="danger"]:hover {{
    background-color: rgba(255, 69, 58, 0.12);
    border-color: {COLORS['danger']};
}}

QPushButton[cssClass="danger"]:pressed {{
    background-color: rgba(255, 69, 58, 0.2);
}}

/* ===== Tree Widget — glass panel ===== */
QTreeWidget {{
    background-color: {COLORS['bg_panel_solid']};
    border: 1px solid {COLORS['border']};
    border-radius: 14px;
    outline: none;
    padding: 6px;
}}

QTreeWidget::item {{
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
    border: 1px solid {COLORS['border']};
    border-radius: 14px;
    gridline-color: {COLORS['border']};
    outline: none;
}}

QTableWidget::item {{
    padding: 4px 8px;
    border-bottom: 1px solid {COLORS['border']};
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
    background-color: {COLORS['text_dim']};
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
    background-color: {COLORS['text_dim']};
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

/* ===== Combo Box — glass ===== */
QComboBox {{
    background-color: {COLORS['bg_input']};
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
    padding: 6px 12px;
    min-height: 18px;
    font-size: 12px;
}}

QComboBox:hover {{
    border-color: {COLORS['border_light']};
}}

QComboBox::drop-down {{
    border: none;
    width: 24px;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_panel_solid']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    selection-background-color: {COLORS['bg_hover']};
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
    border: 1px solid {COLORS['border']};
    border-radius: 12px;
    padding: 6px 12px;
    color: {COLORS['text']};
    font-size: 12px;
}}

QLineEdit:focus {{
    border-color: {COLORS['accent']};
}}

/* ===== Progress Bar — Apple Blue ===== */
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
}}

/* ===== Group Box — glass card ===== */
QGroupBox {{
    border: 1px solid {COLORS['border']};
    border-radius: 14px;
    margin-top: 14px;
    padding: 16px 12px 12px;
    font-weight: 600;
    font-size: 12px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 14px;
    padding: 0 8px;
    color: {COLORS['text']};
}}

/* ===== Tool Tips — glass ===== */
QToolTip {{
    background-color: {COLORS['bg_panel_solid']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    padding: 6px 10px;
    font-size: 11px;
}}

/* ===== Workflow Bar — glass panel ===== */
QWidget[cssClass="workflow-bar"] {{
    background-color: {COLORS['bg_panel_solid']};
    border-bottom: 1px solid {COLORS['border']};
}}
"""


def track_color(index: int) -> str:
    """Return a track color by index (cycles through palette)."""
    colors = COLORS["track_colors"]
    return colors[index % len(colors)]
