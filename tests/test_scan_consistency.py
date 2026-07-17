import json
import os
import subprocess
import tempfile
import unittest

from core.scanner import Scanner
from core.report_status import (
    PASS_STATUS,
    FAIL_STATUS,
    MISSING_SCRIPT_STATUS,
    normalize_report_status,
)


class TestScanConsistency(unittest.TestCase):
    def _make_item(self, code, script_path=None, recommended=None):
        item = {
            "code": code,
            "level": "L1",
            "description": f"Test item {code}",
            "name": f"Test {code}",
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

    def _run_scan(self, items, output_dir):
        scanner = Scanner(items=items, output_dir=output_dir)
        scanner.run()
        import glob
        reports = glob.glob(os.path.join(output_dir, "report_*.json"))
        with open(reports[0], "r", encoding="utf-8") as f:
            return json.load(f)

    def test_config_vs_scan_consistency_same_items_same_result(self):
        items = [
            self._make_item("1.1.1", recommended="PasswordHistorySize: 24"),
            self._make_item("1.1.2", recommended="MaxPasswordAge: 365"),
        ]

        with tempfile.TemporaryDirectory() as out1, tempfile.TemporaryDirectory() as out2:
            r1 = self._run_scan(items, out1)
            r2 = self._run_scan(items, out2)

            for result1, result2 in zip(r1["results"], r2["results"]):
                self.assertEqual(result1["status"], result2["status"],
                    f"Status mismatch: {result1['code']}")
                self.assertEqual(result1["detail"], result2["detail"],
                    f"Detail mismatch: {result1['code']}")

    def test_password_policy_items_consistency(self):
        password_items = [
            self._make_item("1.1.1", recommended="24 or more password(s)"),
            self._make_item("1.1.2", recommended="365 or fewer days, but not 0"),
            self._make_item("1.1.3", recommended="1 or more day(s)"),
        ]

        with tempfile.TemporaryDirectory() as td:
            report = self._run_scan(password_items, td)
            results = report["results"]

            statuses = {r["code"]: r["status"] for r in results}
            self.assertEqual(len(statuses), 3)

            for code in ["1.1.1", "1.1.2", "1.1.3"]:
                self.assertIn(code, statuses)

    def test_report_structure_contains_expected_fields(self):
        items = [
            self._make_item("1.1.1"),
        ]

        with tempfile.TemporaryDirectory() as td:
            report = self._run_scan(items, td)

            self.assertIn("scan_info", report)
            self.assertIn("integrity_hash", report["scan_info"])
            self.assertIn("scan_summary", report)
            self.assertIn("results", report)

            summary = report["scan_summary"]
            for key in ("total", "pass", "fail", "script_missing", "error"):
                self.assertIn(key, summary)

            result = report["results"][0]
            for key in ("code", "level", "description", "suggestion", "status", "timestamp", "detail"):
                self.assertIn(key, result, f"Missing field: {key}")

    def test_status_normalization_is_consistent(self):
        test_cases = [
            ("pass", PASS_STATUS),
            ("Pass", PASS_STATUS),
            ("fail", FAIL_STATUS),
            ("Fail", FAIL_STATUS),
            ("missing_script_path", MISSING_SCRIPT_STATUS),
            ("script_not_found", MISSING_SCRIPT_STATUS),
            ("", FAIL_STATUS),
            (None, FAIL_STATUS),
        ]

        for input_val, expected in test_cases:
            result = normalize_report_status(input_val)
            self.assertEqual(result, expected,
                f"normalize_report_status({input_val!r}) = {result!r}, expected {expected!r}")

    def test_scan_with_passing_script_produces_consistent_detail(self):
        with tempfile.TemporaryDirectory() as td:
            script = self._create_dummy_script(td, "check.ps1", "exit 0")
            item = self._make_item("1.1.1", script_path=script)

            with tempfile.TemporaryDirectory() as out1, tempfile.TemporaryDirectory() as out2:
                r1 = self._run_scan([item], out1)
                r2 = self._run_scan([item], out2)

                self.assertEqual(r1["results"][0]["detail"], "compliant")
                self.assertEqual(r2["results"][0]["detail"], "compliant")
                self.assertEqual(r1["results"][0]["status"], PASS_STATUS)
                self.assertEqual(r2["results"][0]["status"], PASS_STATUS)

    def test_scan_with_failing_script_produces_consistent_detail(self):
        with tempfile.TemporaryDirectory() as td:
            script = self._create_dummy_script(td, "check.ps1", "exit 1")
            item = self._make_item("1.1.1", script_path=script)

            with tempfile.TemporaryDirectory() as out:
                report = self._run_scan([item], out)
                result = report["results"][0]

                self.assertEqual(result["detail"], "noncompliant")
                self.assertEqual(result["status"], FAIL_STATUS)

    def test_integrity_hash_present_and_valid_format(self):
        items = [self._make_item("1.1.1")]

        with tempfile.TemporaryDirectory() as td:
            report = self._run_scan(items, td)

            scan_hash = report["scan_info"]["integrity_hash"]
            self.assertIsInstance(scan_hash, str)
            self.assertEqual(len(scan_hash), 64)
            self.assertTrue(all(c in "0123456789abcdef" for c in scan_hash))


if __name__ == "__main__":
    import unittest
    unittest.main()
