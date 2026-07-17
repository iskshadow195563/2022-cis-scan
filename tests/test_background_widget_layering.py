import os
import tempfile
import unittest

from PyQt5.QtCore import QSettings, Qt
from PyQt5.QtTest import QTest
from PyQt5.QtWidgets import QApplication, QPushButton

from gui.background_manager import BackgroundManager, BackgroundWidget


_GIF_BYTES = (
    b"GIF89a"
    b"\x01\x00\x01\x00"
    b"\x80\x00\x00"
    b"\x00\x00\x00"
    b"\xff\xff\xff"
    b"\x21\xf9\x04\x01\x00\x00\x00\x00"
    b"\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00"
    b"\x02\x02\x4c\x01\x00"
    b"\x3b"
)


class TestBackgroundWidgetLayering(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self):
        self._orig_disable_anim = os.environ.get("PROJECT001_DISABLE_ANIMATED_BACKGROUNDS")
        os.environ["PROJECT001_DISABLE_ANIMATED_BACKGROUNDS"] = "1"
        self._tmpdir = tempfile.TemporaryDirectory()
        self._gif_path = os.path.join(self._tmpdir.name, "bg.gif")
        with open(self._gif_path, "wb") as fh:
            fh.write(_GIF_BYTES)
        self._settings_path = os.path.join(self._tmpdir.name, "settings.ini")
        self._settings = QSettings(self._settings_path, QSettings.IniFormat)
        self._manager = BackgroundManager(background_dir=self._tmpdir.name, settings=self._settings)
        self._widget = BackgroundWidget(self._manager)
        self._widget.resize(480, 320)
        self._button = QPushButton("Run", self._widget)
        self._button.setGeometry(120, 90, 140, 48)
        self._clicks = 0
        self._button.clicked.connect(self._on_click)
        self._widget.show()
        QTest.qWaitForWindowExposed(self._widget)
        QApplication.processEvents()

    def tearDown(self):
        self._manager.clear()
        self._widget.close()
        QApplication.processEvents()
        self._settings.sync()
        if self._orig_disable_anim is None:
            os.environ.pop("PROJECT001_DISABLE_ANIMATED_BACKGROUNDS", None)
        else:
            os.environ["PROJECT001_DISABLE_ANIMATED_BACKGROUNDS"] = self._orig_disable_anim
        self._tmpdir.cleanup()

    def _on_click(self):
        self._clicks += 1

    def test_gif_background_stays_behind_interactive_controls(self):
        self._manager.set_selected_path(self._gif_path)
        QTest.qWait(150)
        QApplication.processEvents()
        self.assertIsNotNone(self._widget._label)
        self.assertTrue(self._widget._label.testAttribute(Qt.WA_TransparentForMouseEvents))
        local_center = self._button.geometry().center()
        self.assertIs(self._widget.childAt(local_center), self._button)
        QTest.mouseClick(self._button, Qt.LeftButton, pos=self._button.rect().center())
        QApplication.processEvents()
        self.assertEqual(self._clicks, 1)
        self.assertEqual(self._widget._label.geometry(), self._widget.rect())
        self.assertTrue(self._widget._label.isVisible())

    def test_gif_background_resizes_with_window_without_covering_button(self):
        self._manager.set_selected_path(self._gif_path)
        QTest.qWait(150)
        self._widget.resize(800, 500)
        QTest.qWait(200)
        QApplication.processEvents()
        self.assertIsNotNone(self._widget._label)
        self.assertEqual(self._widget._label.geometry(), self._widget.rect())
        self.assertIs(self._widget.childAt(self._button.geometry().center()), self._button)
