import os
import unittest
from PyQt5.QtWidgets import QApplication

class TestEnvironmentInfo(unittest.TestCase):
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
    def test_check_environment_shows_os_details_client(self):
        os.environ["OS_PROFILE_OVERRIDE"] = "client:win10"
        from gui.main_window import MainWindow
        w = MainWindow()
        w.check_environment()
        text = w.status_label.text()
        self.assertTrue(("OS:" in text) or ("作業系統：" in text))
        self.assertTrue(("Build:" in text) or ("組建：" in text))
        self.assertTrue(("Arch:" in text) or ("架構：" in text))
    def test_check_environment_shows_os_details_server(self):
        os.environ["OS_PROFILE_OVERRIDE"] = "server:2019"
        from gui.main_window import MainWindow
        w = MainWindow()
        w.check_environment()
        text = w.status_label.text()
        self.assertTrue(("OS:" in text) or ("作業系統：" in text))
        self.assertTrue(("ProductType:" in text) or ("產品類型：" in text))
