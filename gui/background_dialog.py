import os

from PyQt5.QtCore import Qt, QUrl, QPropertyAnimation, QSize
from PyQt5.QtGui import QPixmap, QDesktopServices, QIcon, QImageReader
from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QListWidgetItem,
    QFileDialog,
    QGraphicsOpacityEffect,
)

from core.language_manager import tr
from gui.background_manager import BackgroundManager


class BackgroundDialog(QDialog):
    def __init__(self, manager: BackgroundManager, parent=None):
        super().__init__(parent)
        self.manager = manager
        self.setWindowTitle(tr("bg_title"))
        self.setModal(True)
        self.resize(860, 520)
        self._init_ui()
        self._apply_fade_in()
        self.refresh()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        top = QHBoxLayout()
        title = QLabel(tr("bg_title"))
        title.setStyleSheet("font-size: 16px; font-weight: bold;")
        top.addWidget(title)
        top.addStretch()
        self.btn_close = QPushButton("×")
        self.btn_close.setFixedWidth(28)
        self.btn_close.setToolTip(tr("close"))
        self.btn_close.clicked.connect(self.close)
        top.addWidget(self.btn_close)
        layout.addLayout(top)

        body = QHBoxLayout()

        left = QVBoxLayout()
        self.list_widget = QListWidget()
        self.list_widget.setSelectionMode(QListWidget.SingleSelection)
        self.list_widget.currentItemChanged.connect(self._on_selection_changed)
        left.addWidget(self.list_widget, 1)

        actions = QHBoxLayout()
        self.btn_add = QPushButton(tr("bg_add"))
        self.btn_add.clicked.connect(self.add_image)
        self.btn_open_folder = QPushButton(tr("bg_open_folder"))
        self.btn_open_folder.clicked.connect(self.open_folder)
        self.btn_clear = QPushButton(tr("bg_clear"))
        self.btn_clear.clicked.connect(self.clear_background)
        self.btn_refresh = QPushButton(tr("bg_refresh"))
        self.btn_refresh.clicked.connect(self.refresh)
        actions.addWidget(self.btn_add)
        actions.addWidget(self.btn_open_folder)
        actions.addWidget(self.btn_clear)
        actions.addWidget(self.btn_refresh)
        left.addLayout(actions)

        self.message = QLabel("")
        self.message.setWordWrap(True)
        left.addWidget(self.message)

        body.addLayout(left, 2)

        right = QVBoxLayout()
        self.preview = QLabel("")
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setMinimumWidth(320)
        self.preview.setProperty("card", True)
        right.addWidget(self.preview, 1)
        self.preview_path = QLabel("")
        self.preview_path.setWordWrap(True)
        right.addWidget(self.preview_path)
        body.addLayout(right, 1)

        layout.addLayout(body, 1)

        tip = QLabel(tr("bg_tip"))
        tip.setWordWrap(True)
        tip.setStyleSheet("color: #2c3e50;")
        layout.addWidget(tip)

    def _read_scaled_pixmap(self, path: str, bounds: QSize) -> QPixmap:
        if not path or not bounds.isValid() or bounds.isEmpty():
            return QPixmap()
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        src_size = reader.size()
        if src_size.isValid() and not src_size.isEmpty():
            tw = max(1, int(bounds.width()))
            th = max(1, int(bounds.height()))
            sw = max(1, int(src_size.width()))
            sh = max(1, int(src_size.height()))
            scale = min(tw / sw, th / sh)
            scaled_size = QSize(max(1, int(sw * scale)), max(1, int(sh * scale)))
            reader.setScaledSize(scaled_size)
        img = reader.read()
        if img.isNull():
            return QPixmap()
        return QPixmap.fromImage(img)

    def _apply_fade_in(self):
        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        anim = QPropertyAnimation(eff, b"opacity", self)
        anim.setDuration(160)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.start(QPropertyAnimation.DeleteWhenStopped)

    def refresh(self):
        self.message.setText("")
        current = self.manager.selected_path()
        self.list_widget.blockSignals(True)
        try:
            self.list_widget.clear()
            items = self.manager.list_images()
            for path in items:
                item = QListWidgetItem(os.path.basename(path))
                item.setData(Qt.UserRole, path)
                thumb = self._read_scaled_pixmap(path, QSize(64, 64))
                if not thumb.isNull():
                    item.setIcon(QIcon(thumb.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)))
                self.list_widget.addItem(item)
                if current and os.path.abspath(current) == os.path.abspath(path):
                    self.list_widget.setCurrentItem(item)
        finally:
            self.list_widget.blockSignals(False)
        if not self.list_widget.currentItem():
            self._render_preview(None)

    def _on_selection_changed(self, current, _prev):
        path = current.data(Qt.UserRole) if current else ""
        if path:
            pixmap, err = self.manager._try_load_pixmap_path(path)
            if pixmap is None:
                self.message.setText(tr("bg_invalid", os.path.basename(path), err or ""))
                return
            self.manager.set_selected_path(path)
            self.message.setText(tr("bg_applied", os.path.basename(path)))
            self._render_preview(path)
        else:
            self._render_preview(None)

    def _render_preview(self, path):
        if not path:
            self.preview.setText(tr("bg_no_selection"))
            self.preview.setPixmap(QPixmap())
            self.preview_path.setText("")
            return
        pix = self._read_scaled_pixmap(path, self.preview.size())
        if pix.isNull():
            self.preview.setText(tr("bg_invalid_preview"))
            self.preview.setPixmap(QPixmap())
            self.preview_path.setText(path)
            return
        scaled = pix.scaled(self.preview.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.preview.setPixmap(scaled)
        self.preview.setText("")
        self.preview_path.setText(path)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        item = self.list_widget.currentItem()
        path = item.data(Qt.UserRole) if item else ""
        self._render_preview(path)

    def add_image(self):
        filt = tr("bg_file_filter")
        path, _ = QFileDialog.getOpenFileName(self, tr("bg_add"), "", filt)
        if not path:
            return
        dest, err = self.manager.add_image_from_file(path)
        if dest is None:
            self.message.setText(tr("bg_add_failed", err or ""))
            return
        self.refresh()
        for i in range(self.list_widget.count()):
            it = self.list_widget.item(i)
            if os.path.abspath(it.data(Qt.UserRole)) == os.path.abspath(dest):
                self.list_widget.setCurrentItem(it)
                break

    def open_folder(self):
        self.manager.ensure_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.manager.background_dir))

    def clear_background(self):
        self.manager.clear()
        self.message.setText(tr("bg_cleared"))
        self.list_widget.clearSelection()
        self._render_preview(None)
