import os
import unittest
from PyQt5.QtWidgets import QApplication

class TestItemsVisibleClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
    def setUp(self):
        self._orig = os.environ.get("OS_PROFILE_OVERRIDE")
        os.environ["OS_PROFILE_OVERRIDE"] = "client:win11"
    def tearDown(self):
        if self._orig is None:
            os.environ.pop("OS_PROFILE_OVERRIDE", None)
        else:
            os.environ["OS_PROFILE_OVERRIDE"] = self._orig
    def test_items_container_visible_and_items_loaded(self):
        from gui.main_window import MainWindow
        w = MainWindow()
        w.show()
        self.assertTrue(w.items_container.isVisible())
        self.assertGreater(w.items_table.rowCount(), 0)

    def test_assessment_column_is_populated_for_loaded_rows(self):
        from gui.main_window import MainWindow
        w = MainWindow()
        w.show()
        missing_rows = []
        for row in range(w.items_table.rowCount()):
            assessment_item = w.items_table.item(row, w.COL_ASSESSMENT)
            if assessment_item is None or not assessment_item.text().strip():
                code_item = w.items_table.item(row, w.COL_NUMBER)
                missing_rows.append(code_item.text() if code_item else str(row))
        self.assertEqual(missing_rows, [])
