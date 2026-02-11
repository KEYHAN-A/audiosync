"""AudioSync Pro — Glassmorphism Dark Navy theme (macOS 26 vibes).

Design language:
- Deep navy layered backgrounds with frosted-glass panels
- Cyan/purple accent gradients matching the website brand
- Generous border-radius (circular elements, pill buttons)
- Subtle glow borders, translucent overlays
- All text is bright on dark — never black
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
#  Color Palette — Deep Navy + Cyan / Purple glass
# ---------------------------------------------------------------------------

COLORS = {
    # Backgrounds — layered navy depth
    "bg_deep":          "#050816",       # deepest (main window)
    "bg_dark":          "#0a0e1a",       # panels
    "bg_panel":         "#111827",       # elevated panels
    "bg_card":          "#151c2e",       # card surfaces
    "bg_input":         "#1a2236",       # input fields (visible)
    "bg_hover":         "rgba(56, 189, 248, 0.10)",
    "bg_selected":      "rgba(56, 189, 248, 0.18)",

    # Glass surfaces — translucent
    "glass":            "rgba(21, 28, 46, 0.65)",
    "glass_border":     "rgba(56, 189, 248, 0.12)",
    "glass_hover":      "rgba(56, 189, 248, 0.22)",
    "glass_glow":       "rgba(56, 189, 248, 0.08)",

    # Borders
    "border":           "rgba(56, 189, 248, 0.08)",
    "border_subtle":    "rgba(56, 189, 248, 0.12)",
    "border_light":     "rgba(56, 189, 248, 0.18)",
    "border_bright":    "rgba(56, 189, 248, 0.30)",

    # Text — always bright on dark
    "text":             "#e0e7ff",
    "text_dim":         "#8b95b8",
    "text_bright":      "#f0f4ff",
    "text_muted":       "#5e6a8a",

    # Accent — cyan-blue primary
    "accent":           "#38bdf8",
    "accent_hover":     "#7dd3fc",
    "accent_pressed":   "#0ea5e9",
    "accent_subtle":    "rgba(56, 189, 248, 0.15)",
    "accent_glow":      "rgba(56, 189, 248, 0.25)",

    # Secondary — purple
    "secondary":        "#a78bfa",
    "secondary_hover":  "#c4b5fd",
    "secondary_subtle": "rgba(167, 139, 250, 0.12)",

    # Status
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
#  QSS Stylesheet — Frosted Glass (macOS 26 inspired)
# ---------------------------------------------------------------------------

STYLESHEET = f"""
/* ===== Global Reset ===== */
* {{
    color: {COLORS['text']};
    outline: none;
}}

QWidget {{
    background-color: {COLORS['bg_deep']};
    color: {COLORS['text']};
    font-family: "SF Pro Display", "SF Pro Text", ".AppleSystemUIFont",
                 "Inter", "Segoe UI", "Helvetica Neue", sans-serif;
    font-size: 13px;
    selection-background-color: {COLORS['accent']};
    selection-color: #ffffff;
}}

QMainWindow {{
    background-color: {COLORS['bg_deep']};
}}

/* ===== Menu Bar — frosted glass ===== */
QMenuBar {{
    background-color: {COLORS['bg_panel']};
    color: {COLORS['text']};
    border-bottom: 1px solid {COLORS['border_subtle']};
    padding: 4px 0;
    font-size: 12px;
}}

QMenuBar::item {{
    color: {COLORS['text']};
    padding: 6px 16px;
    border-radius: 10px;
    margin: 2px 3px;
}}

QMenuBar::item:selected {{
    background-color: {COLORS['bg_hover']};
    color: {COLORS['text_bright']};
}}

QMenu {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 14px;
    padding: 8px 0;
}}

QMenu::item {{
    color: {COLORS['text']};
    padding: 8px 36px 8px 18px;
    border-radius: 8px;
    margin: 1px 6px;
}}

QMenu::item:selected {{
    background-color: {COLORS['bg_hover']};
    color: {COLORS['text_bright']};
}}

QMenu::item:disabled {{
    color: {COLORS['text_muted']};
}}

QMenu::separator {{
    height: 1px;
    background: {COLORS['border_subtle']};
    margin: 8px 16px;
}}

/* ===== Buttons — glass pill ===== */
QPushButton {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 12px;
    padding: 8px 20px;
    font-weight: 500;
    font-size: 12px;
    min-height: 18px;
}}

QPushButton:hover {{
    background-color: rgba(56, 189, 248, 0.08);
    border-color: {COLORS['accent']};
    color: {COLORS['text_bright']};
}}

QPushButton:pressed {{
    background-color: rgba(56, 189, 248, 0.12);
    border-color: {COLORS['accent_pressed']};
}}

QPushButton:disabled {{
    color: {COLORS['text_muted']};
    background-color: {COLORS['bg_dark']};
    border-color: {COLORS['border']};
}}

/* Primary — solid accent pill */
QPushButton[cssClass="primary"] {{
    background-color: {COLORS['accent']};
    color: #050816;
    border: none;
    font-weight: 700;
    font-size: 13px;
    border-radius: 16px;
    padding: 9px 30px;
    min-height: 22px;
}}

QPushButton[cssClass="primary"]:hover {{
    background-color: {COLORS['accent_hover']};
}}

QPushButton[cssClass="primary"]:pressed {{
    background-color: {COLORS['accent_pressed']};
}}

QPushButton[cssClass="primary"]:disabled {{
    background-color: {COLORS['border_subtle']};
    color: {COLORS['text_muted']};
}}

/* Accent — same as primary but smaller */
QPushButton[cssClass="accent"] {{
    background-color: {COLORS['accent']};
    color: #050816;
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
    background-color: {COLORS['border_subtle']};
    color: {COLORS['text_muted']};
}}

/* Secondary — outlined purple */
QPushButton[cssClass="secondary"] {{
    background-color: {COLORS['secondary_subtle']};
    color: {COLORS['secondary']};
    border: 1px solid rgba(167, 139, 250, 0.25);
    font-weight: 600;
    font-size: 12px;
    border-radius: 16px;
    padding: 8px 22px;
    min-height: 22px;
}}

QPushButton[cssClass="secondary"]:hover {{
    background-color: rgba(167, 139, 250, 0.18);
    color: {COLORS['secondary_hover']};
    border-color: rgba(167, 139, 250, 0.40);
}}

QPushButton[cssClass="secondary"]:pressed {{
    background-color: rgba(167, 139, 250, 0.25);
}}

QPushButton[cssClass="secondary"]:disabled {{
    background-color: transparent;
    color: {COLORS['text_muted']};
    border-color: {COLORS['border']};
}}

/* Danger — ghost red */
QPushButton[cssClass="danger"] {{
    background-color: transparent;
    color: {COLORS['danger']};
    border: 1px solid transparent;
    font-weight: 500;
}}

QPushButton[cssClass="danger"]:hover {{
    background-color: rgba(248, 113, 113, 0.10);
    border-color: rgba(248, 113, 113, 0.30);
    color: {COLORS['danger_hover']};
}}

QPushButton[cssClass="danger"]:pressed {{
    background-color: rgba(248, 113, 113, 0.18);
}}

/* ===== Scroll Area ===== */
QScrollArea {{
    background-color: transparent;
    border: none;
}}

QScrollArea > QWidget > QWidget {{
    background-color: transparent;
}}

/* ===== Splitter ===== */
QSplitter::handle {{
    background-color: {COLORS['border_subtle']};
}}

QSplitter::handle:vertical {{
    height: 3px;
    margin: 0 16px;
}}

QSplitter::handle:horizontal {{
    width: 1px;
}}

/* ===== Table Widget — glass panel ===== */
QTableWidget {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 16px;
    gridline-color: {COLORS['border_subtle']};
    outline: none;
    alternate-background-color: {COLORS['bg_dark']};
}}

QTableWidget::item {{
    color: {COLORS['text']};
    padding: 6px 10px;
    border-bottom: 1px solid {COLORS['border']};
}}

QTableWidget::item:selected {{
    background-color: {COLORS['bg_selected']};
    color: {COLORS['text_bright']};
}}

QTableWidgetItem {{
    color: {COLORS['text']};
}}

QHeaderView {{
    background-color: transparent;
}}

QHeaderView::section {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_dim']};
    border: none;
    border-bottom: 1px solid {COLORS['border_subtle']};
    padding: 8px 12px;
    font-size: 10px;
    font-weight: 600;
    letter-spacing: 0.8px;
    text-transform: uppercase;
}}

/* ===== Scroll Bars — ultra-thin glass ===== */
QScrollBar:vertical {{
    background-color: transparent;
    width: 6px;
    margin: 6px 1px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: rgba(56, 189, 248, 0.15);
    border-radius: 3px;
    min-height: 40px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: rgba(56, 189, 248, 0.30);
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    height: 0;
    background: transparent;
}}

QScrollBar:horizontal {{
    background-color: transparent;
    height: 6px;
    margin: 1px 6px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: rgba(56, 189, 248, 0.15);
    border-radius: 3px;
    min-width: 40px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: rgba(56, 189, 248, 0.30);
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    width: 0;
    background: transparent;
}}

/* ===== Status Bar — subtle glass ===== */
QStatusBar {{
    background-color: {COLORS['bg_panel']};
    border-top: 1px solid {COLORS['border']};
    color: {COLORS['text_dim']};
    font-size: 11px;
    padding: 4px 14px;
}}

QStatusBar QLabel {{
    color: {COLORS['text_dim']};
    background: transparent;
}}

/* ===== Combo Box — glass ===== */
QComboBox {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 12px;
    padding: 7px 14px;
    min-height: 20px;
    font-size: 12px;
}}

QComboBox:hover {{
    border-color: {COLORS['accent']};
}}

QComboBox::drop-down {{
    border: none;
    width: 28px;
}}

QComboBox::down-arrow {{
    image: none;
    border: none;
}}

QComboBox QAbstractItemView {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 12px;
    selection-background-color: {COLORS['bg_hover']};
    selection-color: {COLORS['text_bright']};
    padding: 6px;
    outline: none;
}}

QComboBox QAbstractItemView::item {{
    color: {COLORS['text']};
    padding: 6px 12px;
    border-radius: 8px;
    min-height: 24px;
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: {COLORS['bg_hover']};
    color: {COLORS['text_bright']};
}}

/* ===== Spin Box — glass ===== */
QSpinBox, QDoubleSpinBox {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 12px;
    padding: 6px 12px;
    font-size: 12px;
    min-height: 20px;
}}

QSpinBox:hover, QDoubleSpinBox:hover {{
    border-color: {COLORS['accent']};
}}

QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {COLORS['accent']};
}}

QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background: transparent;
    border: none;
    width: 20px;
}}

QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: none;
}}

QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: none;
}}

/* ===== Labels ===== */
QLabel {{
    background-color: transparent;
    color: {COLORS['text']};
}}

QLabel[cssClass="heading"] {{
    font-size: 15px;
    font-weight: 600;
    color: {COLORS['text_bright']};
    letter-spacing: -0.3px;
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
    padding: 8px 14px;
    color: {COLORS['text']};
    font-size: 12px;
}}

QLineEdit:focus {{
    border-color: {COLORS['accent']};
}}

QLineEdit:read-only {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text_dim']};
}}

/* ===== Progress Bar — Cyan accent, rounded ===== */
QProgressBar {{
    background-color: {COLORS['bg_input']};
    border: none;
    border-radius: 8px;
    text-align: center;
    color: {COLORS['text']};
    font-size: 11px;
    font-weight: 600;
    min-height: 16px;
}}

QProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 {COLORS['accent']}, stop:1 {COLORS['secondary']});
    border-radius: 8px;
}}

/* ===== Dialog — glass ===== */
QDialog {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text']};
}}

/* ===== Message Box — force light text ===== */
QMessageBox {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text']};
}}

QMessageBox QLabel {{
    color: {COLORS['text']};
    font-size: 13px;
    background: transparent;
}}

QMessageBox QPushButton {{
    color: {COLORS['text']};
    min-width: 80px;
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

/* ===== File Dialog — force colors ===== */
QFileDialog {{
    background-color: {COLORS['bg_dark']};
    color: {COLORS['text']};
}}

QFileDialog QLabel {{
    color: {COLORS['text']};
}}

QFileDialog QLineEdit {{
    color: {COLORS['text']};
}}

QFileDialog QPushButton {{
    color: {COLORS['text']};
}}

/* ===== Dialog Button Box ===== */
QDialogButtonBox QPushButton {{
    color: {COLORS['text']};
    min-width: 90px;
    padding: 8px 20px;
}}

/* ===== Group Box — glass card ===== */
QGroupBox {{
    background-color: {COLORS['bg_card']};
    border: 1px solid {COLORS['border_subtle']};
    border-radius: 16px;
    margin-top: 18px;
    padding: 20px 14px 14px;
    font-weight: 600;
    font-size: 12px;
    color: {COLORS['text']};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    left: 16px;
    padding: 0 10px;
    color: {COLORS['text_bright']};
    background-color: {COLORS['bg_card']};
    border-radius: 6px;
}}

/* ===== Tool Tips — glass ===== */
QToolTip {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 10px;
    padding: 8px 12px;
    font-size: 11px;
}}

/* ===== Workflow Bar — glass panel ===== */
QWidget[cssClass="workflow-bar"] {{
    background-color: {COLORS['bg_panel']};
    border-bottom: 1px solid {COLORS['border_subtle']};
}}

/* ===== Form Layout Labels ===== */
QFormLayout QLabel {{
    color: {COLORS['text']};
}}

/* ===== Tab Widget ===== */
QTabWidget::pane {{
    background-color: {COLORS['bg_dark']};
    border: 1px solid {COLORS['border_subtle']};
    border-radius: 14px;
}}

QTabBar::tab {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text_dim']};
    border: 1px solid {COLORS['border']};
    border-radius: 10px;
    padding: 8px 20px;
    margin: 2px;
}}

QTabBar::tab:selected {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text_bright']};
    border-color: {COLORS['border_light']};
}}

/* ===== Check Box ===== */
QCheckBox {{
    color: {COLORS['text']};
    spacing: 8px;
}}

QCheckBox::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 5px;
    border: 2px solid {COLORS['border_light']};
    background-color: {COLORS['bg_input']};
}}

QCheckBox::indicator:checked {{
    background-color: {COLORS['accent']};
    border-color: {COLORS['accent']};
}}

/* ===== Radio Button ===== */
QRadioButton {{
    color: {COLORS['text']};
    spacing: 8px;
}}

QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border-radius: 9px;
    border: 2px solid {COLORS['border_light']};
    background-color: {COLORS['bg_input']};
}}

QRadioButton::indicator:checked {{
    background-color: {COLORS['accent']};
    border-color: {COLORS['accent']};
}}

/* ===== Text Edit / Plain Text ===== */
QTextEdit, QPlainTextEdit {{
    background-color: {COLORS['bg_input']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_light']};
    border-radius: 12px;
    padding: 8px;
}}

/* ===== List / Tree Views ===== */
QListView, QTreeView {{
    background-color: {COLORS['bg_card']};
    color: {COLORS['text']};
    border: 1px solid {COLORS['border_subtle']};
    border-radius: 12px;
    outline: none;
}}

QListView::item, QTreeView::item {{
    color: {COLORS['text']};
    padding: 4px 8px;
    border-radius: 6px;
}}

QListView::item:selected, QTreeView::item:selected {{
    background-color: {COLORS['bg_selected']};
    color: {COLORS['text_bright']};
}}

QListView::item:hover, QTreeView::item:hover {{
    background-color: {COLORS['bg_hover']};
}}
"""


def track_color(index: int) -> str:
    """Return a track color by index (cycles through palette)."""
    colors = COLORS["track_colors"]
    return colors[index % len(colors)]
