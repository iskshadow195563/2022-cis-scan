from PyQt5.QtCore import QSettings


THEME_TOKENS = {
    "light": {
        "text_primary": "#1f2937",
        "text_muted": "#334155",
        "text_inverse": "#f8fafc",
        "text_button": "#0f172a",
        "bg_panel": "rgba(255, 255, 255, 0.40)",
        "bg_panel_hover": "rgba(255, 255, 255, 0.48)",
        "bg_panel_focus": "rgba(255, 255, 255, 0.50)",
        "bg_panel_disabled": "rgba(248, 250, 252, 0.32)",
        "bg_button": "rgba(52, 152, 219, 0.44)",
        "bg_button_hover": "rgba(41, 128, 185, 0.50)",
        "bg_button_focus": "rgba(31, 97, 141, 0.48)",
        "bg_button_disabled": "rgba(189, 195, 199, 0.34)",
        "bg_accent": "rgba(108, 92, 231, 0.45)",
        "bg_accent_hover": "rgba(90, 75, 209, 0.50)",
        "bg_success": "rgba(46, 204, 113, 0.42)",
        "bg_warning": "rgba(241, 196, 15, 0.42)",
        "bg_error": "rgba(231, 76, 60, 0.42)",
        "border_default": "rgba(15, 23, 42, 0.30)",
        "border_hover": "rgba(15, 23, 42, 0.42)",
        "border_focus": "rgba(37, 99, 235, 0.50)",
        "border_disabled": "rgba(100, 116, 139, 0.28)",
        "shadow": "rgba(15, 23, 42, 0.20)",
        "selection_bg": "rgba(37, 99, 235, 0.86)",
    },
    "dark": {
        "text_primary": "#f1f5f9",
        "text_muted": "#cbd5e1",
        "text_inverse": "#0b1220",
        "text_button": "#f8fafc",
        "bg_panel": "rgba(15, 23, 42, 0.40)",
        "bg_panel_hover": "rgba(30, 41, 59, 0.48)",
        "bg_panel_focus": "rgba(51, 65, 85, 0.50)",
        "bg_panel_disabled": "rgba(15, 23, 42, 0.32)",
        "bg_button": "rgba(59, 130, 246, 0.44)",
        "bg_button_hover": "rgba(37, 99, 235, 0.50)",
        "bg_button_focus": "rgba(29, 78, 216, 0.48)",
        "bg_button_disabled": "rgba(71, 85, 105, 0.34)",
        "bg_accent": "rgba(129, 140, 248, 0.45)",
        "bg_accent_hover": "rgba(99, 102, 241, 0.50)",
        "bg_success": "rgba(34, 197, 94, 0.42)",
        "bg_warning": "rgba(245, 158, 11, 0.42)",
        "bg_error": "rgba(239, 68, 68, 0.42)",
        "border_default": "rgba(148, 163, 184, 0.34)",
        "border_hover": "rgba(148, 163, 184, 0.44)",
        "border_focus": "rgba(96, 165, 250, 0.50)",
        "border_disabled": "rgba(100, 116, 139, 0.30)",
        "shadow": "rgba(2, 6, 23, 0.28)",
        "selection_bg": "rgba(59, 130, 246, 0.86)",
    },
}


def resolve_theme_name(qapp=None):
    settings = QSettings("HKIIT", "WindowsSecurityAuditor")
    pref = (settings.value("ui/theme", "auto") or "auto").lower()
    if pref in ("light", "dark"):
        return pref
    if qapp is not None:
        v = qapp.palette().window().color().value()
        return "dark" if v < 128 else "light"
    return "light"


def build_theme_stylesheet(theme_name):
    t = THEME_TOKENS.get(theme_name, THEME_TOKENS["light"])
    return f"""
QMainWindow {{
    background-color: transparent;
}}
QDialog {{
    background-color: {t["bg_panel"]};
    color: {t["text_primary"]};
}}
QLabel {{
    color: {t["text_primary"]};
}}
QPushButton {{
    background-color: {t["bg_button"]};
    color: {t["text_button"]};
    border: 1px solid {t["border_default"]};
    border-radius: 8px;
    padding: 8px 14px;
    font-size: 14px;
    font-weight: bold;
}}
QPushButton:hover {{
    background-color: {t["bg_button_hover"]};
    border-color: {t["border_hover"]};
}}
QPushButton:focus {{
    background-color: {t["bg_button_focus"]};
    border-color: {t["border_focus"]};
}}
QPushButton:disabled {{
    background-color: {t["bg_button_disabled"]};
    border-color: {t["border_disabled"]};
    color: {t["text_muted"]};
}}
QPushButton#helpButton {{
    background-color: {t["bg_accent"]};
}}
QPushButton#helpButton:hover {{
    background-color: {t["bg_accent_hover"]};
}}
QPushButton#bgButton {{
    background-color: {t["bg_success"]};
}}
QPushButton#bgButton:hover {{
    background-color: {t["bg_success"]};
    border-color: {t["border_hover"]};
}}
QPushButton#applyDefaultsButton {{
    background-color: {t["bg_warning"]};
}}
QPushButton#applyDefaultsButton:hover {{
    background-color: {t["bg_warning"]};
    border-color: {t["border_hover"]};
}}
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QListWidget, QTableWidget, QTextBrowser {{
    background-color: {t["bg_panel"]};
    color: {t["text_primary"]};
    border: 1px solid {t["border_default"]};
    border-radius: 8px;
    selection-background-color: {t["selection_bg"]};
}}
QTableWidget::item:selected, QListWidget::item:selected {{
    background-color: {t["selection_bg"]};
    color: {t["text_inverse"]};
}}
QTableWidget::item:selected:active, QListWidget::item:selected:active {{
    background-color: {t["selection_bg"]};
    color: {t["text_inverse"]};
}}
QLineEdit:hover, QTextEdit:hover, QPlainTextEdit:hover, QComboBox:hover, QListWidget:hover, QTableWidget:hover, QTextBrowser:hover {{
    background-color: {t["bg_panel_hover"]};
    border-color: {t["border_hover"]};
}}
QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QListWidget:focus, QTableWidget:focus, QTextBrowser:focus {{
    background-color: {t["bg_panel_focus"]};
    border-color: {t["border_focus"]};
}}
QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled, QComboBox:disabled, QListWidget:disabled, QTableWidget:disabled, QTextBrowser:disabled {{
    background-color: {t["bg_panel_disabled"]};
    border-color: {t["border_disabled"]};
    color: {t["text_muted"]};
}}
QComboBox QAbstractItemView {{
    background-color: {t["bg_panel_focus"]};
    border: 1px solid {t["border_hover"]};
    color: {t["text_primary"]};
}}
QHeaderView::section {{
    background-color: {t["bg_panel_hover"]};
    color: {t["text_primary"]};
    border: 1px solid {t["border_default"]};
    padding: 6px;
}}
QTableWidget::item {{
    background-color: {t["bg_panel"]};
}}
QTableWidget::item:hover {{
    background-color: {t["bg_panel_hover"]};
}}
QProgressBar {{
    border: 1px solid {t["border_default"]};
    border-radius: 8px;
    text-align: center;
    background-color: {t["bg_panel"]};
    color: {t["text_primary"]};
}}
QProgressBar::chunk {{
    background-color: {t["bg_success"]};
    border-radius: 8px;
}}
QCheckBox {{
    color: {t["text_primary"]};
    spacing: 8px;
}}
QCheckBox:disabled {{
    color: {t["text_muted"]};
}}
QScrollArea {{
    border: 1px solid {t["border_default"]};
    border-radius: 8px;
    background-color: {t["bg_panel"]};
}}
QWidget[card="true"] {{
    background-color: {t["bg_panel"]};
    border: 1px solid {t["border_default"]};
    border-radius: 10px;
}}
QWidget[card="true"]:hover {{
    background-color: {t["bg_panel_hover"]};
    border-color: {t["border_hover"]};
}}
QWidget[card="true"]:focus {{
    background-color: {t["bg_panel_focus"]};
    border-color: {t["border_focus"]};
}}
QWidget[card="true"]:disabled {{
    background-color: {t["bg_panel_disabled"]};
    border-color: {t["border_disabled"]};
}}
"""
