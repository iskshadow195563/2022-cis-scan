import json
import os
import tempfile
import unittest
from PyQt5.QtWidgets import QApplication

class TestReportFilteringClient(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])
    def setUp(self):
        self._orig = os.environ.get("OS_PROFILE_OVERRIDE")
        os.environ["OS_PROFILE_OVERRIDE"] = "client:win10"
    def tearDown(self):
        if self._orig is None:
            os.environ.pop("OS_PROFILE_OVERRIDE", None)
        else:
            os.environ["OS_PROFILE_OVERRIDE"] = self._orig
    def test_summary_only_pass_fail(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = os.path.join(tmp_dir, "sample_client_report.json")
            data = {
                "scan_info": {"date": "2026-01-01", "time": "00:00:00"},
                "results": [
                    {"code": "A", "level": "L1", "description": "desc", "status": "Pass"},
                    {"code": "B", "level": "L1", "description": "desc", "status": "Fail"},
                    {"code": "C", "level": "L1", "description": "desc", "status": "Error"},
                    {"code": "D", "level": "L1", "description": "desc", "status": "Not Supported"},
                    {"code": "E", "level": "L1", "description": "desc", "status": "Not Checked"},
                ]
            }
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
            from gui.report_window import ReportWindow
            w = ReportWindow(tmp_path)
            rows = w.build_summary_rows()
            labels = [r[0] for r in rows]
            has_pass = any(("Pass" in lbl) or ("通過" in lbl) for lbl in labels)
            has_fail = any(("Fail" in lbl) or ("不通過" in lbl) or ("失敗" in lbl) for lbl in labels)
            self.assertTrue(has_pass)
            self.assertTrue(has_fail)
            self.assertEqual(len(rows), 6)
            statuses = []
            for i in range(w.table.rowCount()):
                item = w.table.item(i, 5)
                statuses.append(item.text())
            ok = all(
                any(term in s for term in ("Pass", "Fail", "通過", "不通過", "Error", "錯誤", "Not Supported", "Not Checked", "不支持", "未作檢查", "Script Missing", "腳本缺失"))
                for s in statuses
            )
            self.assertTrue(ok)
            self.assertEqual([item["status"] for item in w.report_data["results"]], ["Pass", "Fail", "Error", "Not Supported", "Not Supported"])
            self.assertEqual(w.get_pie_counts(), (1, 4))
            self.assertAlmostEqual(w.calculate_score(), 20.0)
            self.assertEqual(len(w.ax.patches), 2)
