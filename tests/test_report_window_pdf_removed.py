import json
import os
import unittest
from PyQt5.QtWidgets import QApplication
from gui.report_window import ReportWindow


class TestReportWindowPdfRemoved(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_pdf_export_button_and_method_removed(self):
        tmp_path = os.path.join(os.getcwd(), "results", "sample_report.json")
        os.makedirs(os.path.dirname(tmp_path), exist_ok=True)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump({"scan_info": {"date": "2026-01-01", "time": "00:00:00"}, "results": []}, f)
        window = ReportWindow(tmp_path)
        self.assertFalse(hasattr(window, "btn_export_pdf"))
        self.assertFalse(hasattr(window, "export_pdf"))
