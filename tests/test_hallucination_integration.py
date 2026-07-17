import glob
import json
import os
import tempfile
import unittest

from core.scanner import Scanner
from core.hallucination_detector import HallucinationDetector
from core.hallucination_types import HallucinationReport, HallucinationSeverity


class TestHallucinationIntegration(unittest.TestCase):
    def _make_item(self, code, script_path=None, level="L1", description=None, name=None, recommended=None):
        item = {
            "code": code,
            "level": level,
            "description": description or f"Test item {code}",
            "name": name or f"Test {code}",
            "recommended": recommended or "expected_value",
        }
        if script_path:
            item["script_path"] = script_path
        return item

    def _create_dummy_script(self, directory, name, content="exit 0"):
        script_path = os.path.join(directory, name)
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(content)
        return script_path

    def test_hallucination_detector_in_standalone_mode(self):
        report_data = {
            "scan_info": {
                "date": "2026-01-01",
                "time": "00:00:00",
                "nowtime": "2026-01-01T00:00:00",
            },
            "scan_summary": {
                "total": 3,
                "pass": 2,
                "fail": 1,
                "script_missing": 0,
                "error": 0,
            },
            "results": [
                {"code": "1.1.1", "level": "L1", "description": "Enforce password history",
                 "status": "Pass", "detail": "compliant", "suggestion": "Set it",
                 "timestamp": "2026-01-01T00:00:00"},
                {"code": "1.1.2", "level": "L1", "description": "Max password age",
                 "status": "Fail", "detail": "noncompliant", "suggestion": "Set it",
                 "timestamp": "2026-01-01T00:00:00"},
                {"code": "1.1.3", "level": "L1", "description": "Min password length",
                 "status": "Pass", "detail": "compliant", "suggestion": "Set it",
                 "timestamp": "2026-01-01T00:00:00"},
            ],
        }

        with tempfile.TemporaryDirectory() as td:
            detector = HallucinationDetector(output_dir=td)
            report = detector.detect(report_data)
            saved_path = detector.save_report(report)
            detector.close()

            self.assertIsInstance(report, HallucinationReport)
            self.assertGreaterEqual(report.confidence_score, 0.0)
            self.assertLessEqual(report.confidence_score, 1.0)

            if saved_path:
                self.assertTrue(os.path.exists(saved_path))

    def test_hallucination_detector_detects_empty_code(self):
        report_data = {
            "scan_info": {"date": "2026-01-01", "time": "00:00:00"},
            "scan_summary": {"total": 1, "pass": 0, "fail": 1, "script_missing": 0, "error": 0},
            "results": [
                {"code": "", "level": "L1", "description": "test",
                 "status": "Fail", "suggestion": "test", "detail": "test",
                 "timestamp": "2026-01-01T00:00:00"},
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            detector = HallucinationDetector(output_dir=td)
            report = detector.detect(report_data)
            detector.close()
            self.assertGreaterEqual(len(report.issues), 1)
            critical = [i for i in report.issues if i.severity == HallucinationSeverity.CRITICAL]
            self.assertGreaterEqual(len(critical), 1)

    def test_hallucination_detector_with_item_cross_validation(self):
        items = [
            {"code": "1.1.1", "level": "L1", "description": "Enforce password history"},
        ]
        report_data = {
            "scan_info": {"date": "2026-01-01", "time": "00:00:00",
                          "nowtime": "2026-01-01T00:00:00"},
            "scan_summary": {"total": 1, "pass": 1, "fail": 0, "script_missing": 0, "error": 0},
            "results": [
                {"code": "1.1.1", "level": "L1", "description": "Enforce password history",
                 "status": "Pass", "detail": "compliant", "suggestion": "Set it",
                 "timestamp": "2026-01-01T00:00:00"},
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            detector = HallucinationDetector(output_dir=td)
            report = detector.detect(report_data, items=items)
            detector.close()
            self.assertGreaterEqual(report.confidence_score, 0.65)

    def test_hallucination_detector_finds_duplicate_codes(self):
        report_data = {
            "scan_info": {"date": "2026-01-01", "time": "00:00:00"},
            "scan_summary": {"total": 2, "pass": 1, "fail": 1, "script_missing": 0, "error": 0},
            "results": [
                {"code": "1.1.1", "level": "L1", "status": "Pass", "detail": "x",
                 "description": "a", "suggestion": "a", "timestamp": "t"},
                {"code": "1.1.1", "level": "L1", "status": "Fail", "detail": "y",
                 "description": "a", "suggestion": "a", "timestamp": "t"},
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            detector = HallucinationDetector(output_dir=td)
            report = detector.detect(report_data)
            detector.close()
            dup_issues = [i for i in report.issues if "duplicate" in i.message.lower()]
            self.assertGreaterEqual(len(dup_issues), 1)

    def test_scanner_generates_hallucination_report(self):
        with tempfile.TemporaryDirectory() as td:
            items = [
                self._make_item("1.1.1"),
                self._make_item("1.1.2"),
            ]
            scanner = Scanner(items=items, output_dir=td, enable_hallucination_detection=True)
            scanner.run()

            scan_reports = glob.glob(os.path.join(td, "report_*.json"))
            self.assertEqual(len(scan_reports), 1)

            h_reports = glob.glob(os.path.join(td, "hallucination_*.json"))
            self.assertGreaterEqual(len(h_reports), 1)

            with open(h_reports[0], "r", encoding="utf-8") as f:
                h_data = json.load(f)

            self.assertIn("severity_counts", h_data)
            self.assertIn("category_counts", h_data)
            self.assertIn("confidence_score", h_data)
            self.assertIn("issues", h_data)

    def test_hallucination_detector_handles_malformed_report(self):
        report_data = {"not_results": 123}
        with tempfile.TemporaryDirectory() as td:
            detector = HallucinationDetector(output_dir=td)
            report = detector.detect(report_data)
            detector.close()
            self.assertIsInstance(report, HallucinationReport)
            critical = [i for i in report.issues if i.severity == HallucinationSeverity.CRITICAL]
            self.assertGreaterEqual(len(critical), 1)

    def test_scanner_with_detection_disabled_does_not_generate_h_report(self):
        with tempfile.TemporaryDirectory() as td:
            items = [self._make_item("1.1.1")]
            scanner = Scanner(items=items, output_dir=td, enable_hallucination_detection=False)
            scanner.run()
            h_reports = glob.glob(os.path.join(td, "hallucination_*.json"))
            self.assertEqual(len(h_reports), 0)

    def test_detector_confidence_score_decreases_with_more_issues(self):
        clean = {
            "scan_info": {"date": "2026-01-01", "time": "00:00:00",
                          "nowtime": "2026-01-01T00:00:00"},
            "scan_summary": {"total": 3, "pass": 3, "fail": 0, "script_missing": 0, "error": 0},
            "results": [
                {"code": f"1.1.{i}", "level": "L1", "description": "desc",
                 "status": "Pass", "detail": "compliant", "suggestion": "Set s",
                 "timestamp": "2026-01-01T00:00:00"} for i in range(1, 4)
            ],
        }
        dirty = {
            "scan_info": {"date": "2026-01-01", "time": "00:00:00"},
            "scan_summary": {"total": 100, "pass": 99, "fail": 0, "script_missing": 0, "error": 0},
            "results": [
                {"code": "", "level": "", "description": "",
                 "status": "", "suggestion": "", "detail": "",
                 "timestamp": ""},
                {"code": "x", "level": "L3", "description": "",
                 "status": "bad", "suggestion": "", "detail": "",
                 "timestamp": ""},
            ],
        }
        with tempfile.TemporaryDirectory() as td_clean, tempfile.TemporaryDirectory() as td_dirty:
            detector_clean = HallucinationDetector(output_dir=td_clean)
            clean_report = detector_clean.detect(clean)
            detector_clean.close()
            detector_dirty = HallucinationDetector(output_dir=td_dirty)
            dirty_report = detector_dirty.detect(dirty)
            detector_dirty.close()
            self.assertGreater(clean_report.confidence_score, dirty_report.confidence_score)

    def test_detector_issues_to_dict_serializable(self):
        report_data = {
            "scan_info": {"date": "2026-01-01", "time": "00:00:00"},
            "scan_summary": {"total": 1, "pass": 0, "fail": 1, "script_missing": 0, "error": 0},
            "results": [
                {"code": "1.1.1", "level": "L1", "description": "test",
                 "status": "Fail", "detail": "test", "suggestion": "test",
                 "timestamp": "2026-01-01T00:00:00"},
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            detector = HallucinationDetector(output_dir=td)
            report = detector.detect(report_data)
            detector.close()
            d = report.to_dict()
            self.assertIsInstance(d, dict)
            self.assertIn("issues", d)
            self.assertIsInstance(d["issues"], list)


if __name__ == "__main__":
    unittest.main()
