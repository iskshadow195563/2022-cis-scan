import os
import unittest
from PyQt5.QtWidgets import QApplication
from unittest.mock import patch

class TestLegacyModalExit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
    def setUp(self):
        self._orig = os.environ.get("OS_PROFILE_OVERRIDE")
        os.environ["OS_PROFILE_OVERRIDE"] = "legacy:win7"
    def tearDown(self):
        if self._orig is None:
            os.environ.pop("OS_PROFILE_OVERRIDE", None)
        else:
            os.environ["OS_PROFILE_OVERRIDE"] = self._orig
    def test_modal_auto_exit(self):
        from core.os_detection import show_legacy_block_and_exit
        with patch("PyQt5.QtCore.QTimer.singleShot", side_effect=lambda ms, fn: fn()):
            with self.assertRaises(SystemExit):
                show_legacy_block_and_exit(QApplication.instance())
