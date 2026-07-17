import os
import unittest
from PyQt5.QtWidgets import QApplication

class TestUIVisibilityByOS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
    def setUp(self):
        self._orig = os.environ.get("OS_PROFILE_OVERRIDE")
    def tearDown(self):
        if self._orig is None:
            os.environ.pop("OS_PROFILE_OVERRIDE", None)
        else:
            os.environ["OS_PROFILE_OVERRIDE"] = self._orig
    def test_client_hides_server_ui(self):
        os.environ["OS_PROFILE_OVERRIDE"] = "client:win11"
        from gui.main_window import MainWindow
        w = MainWindow()
        w.show()
        self.assertTrue(w.items_container.isVisible())
        self.assertFalse(w.btn_apply_defaults.isVisible())
        self.assertFalse(w.btn_import_ps.isVisible())
        self.assertFalse(w.btn_delete_ps.isVisible())
    def test_server_shows_server_ui(self):
        os.environ["OS_PROFILE_OVERRIDE"] = "server:2022"
        from gui.main_window import MainWindow
        w = MainWindow()
        w.show()
        self.assertTrue(w.items_container.isVisible())
        self.assertTrue(w.btn_apply_defaults.isVisible())
        self.assertTrue(w.btn_run.isVisible())
        self.assertTrue(w.btn_cancel.isVisible())
