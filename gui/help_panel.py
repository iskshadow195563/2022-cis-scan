import os
from PyQt5.QtCore import Qt, QPropertyAnimation
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextBrowser,
    QGraphicsOpacityEffect,
)

from core.language_manager import tr, lang_manager


class HelpPanel(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("help_title"))
        self.setModal(True)
        self.setAccessibleName(tr("help_accessible_name"))
        self.setAccessibleDescription(tr("help_accessible_desc"))
        # Popup style allows click-outside-to-close on desktop; still has close button.
        self.setWindowFlags(self.windowFlags() | Qt.Popup)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.resize(640, 420)
        self._init_ui()
        self._apply_fade_in()
        self.load_content()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        header = QHBoxLayout()
        title = QLabel(tr("help_title"))
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        header.addWidget(title)
        header.addStretch()
        self.btn_close = QPushButton("×")
        self.btn_close.setFixedWidth(28)
        self.btn_close.setToolTip(tr("close"))
        self.btn_close.setAccessibleName(tr("close"))
        self.btn_close.clicked.connect(self.close)
        header.addWidget(self.btn_close)
        layout.addLayout(header)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(True)
        self.browser.setAccessibleName(tr("help_content_accessible_name"))
        self.browser.setAccessibleDescription(tr("help_content_accessible_desc"))
        layout.addWidget(self.browser, 1)

    def _apply_fade_in(self):
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(160)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def load_content(self):
        lang = getattr(lang_manager, "current_language", "en") or "en"
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        help_dir = os.path.join(base_dir, "data", "help")
        # Try language-specific first, then fall back to English
        candidates = [
            os.path.join(help_dir, f"help_{lang}.html"),
            os.path.join(help_dir, "help_en.html"),
        ]
        for path in candidates:
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        self.browser.setHtml(f.read())
                        return
                except Exception:
                    pass
        # Fallback minimal content
        self.browser.setHtml(f"<h3>{tr('help')}</h3><p>{tr('help_missing')}</p>")
