import glob
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from core.scanner import Scanner
from core.report_status import (
    PASS_STATUS,
    FAIL_STATUS,
    ERROR_STATUS,
    MISSING_SCRIPT_STATUS,
    SCRIPT_ERROR_STATUS,
    UNSUPPORTED_STATUS,
    normalize_report_status,
)


class TestScanDeterminism(unittest.TestCase):
    def _make_item(self, code, script_path=None):
        item = {
            "code": code,
            "level": "L1",
            "description": f"Test item {code}",
            "name": f"Test {code}",
            "recommended": "expected_value",
        }
        if script_path:
            item["script_path"] = script_path
        return item

    def _run_scan_and_get_results(self, items, output_dir, subprocess_run=None):
        scanner = Scanner(items=items, output_dir=output_dir, subprocess_run=subprocess_run)
        scanner.run()
        reports = glob.glob(os.path.join(output_dir, "report_*.json"))
        self.assertEqual(len(reports), 1, f"Expected 1 report, got {len(reports)}")
        with open(reports[0], "r", encoding="utf-8") as f:
            return json.load(f)

    def _create_dummy_script(self, directory, name, content="exit 0"):
        script_path = os.path.join(directory, name)
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(content)
        return script_path

    def test_all_items_without_scripts_produce_identical_results(self):
        items = [self._make_item(f"1.1.{i}") for i in range(1, 11)]

        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            report1 = self._run_scan_and_get_results(items, td1)
            report2 = self._run_scan_and_get_results(items, td2)

            results1 = report1["results"]
            results2 = report2["results"]

            self.assertEqual(len(results1), len(items))
            self.assertEqual(len(results2), len(items))

            for r1, r2 in zip(results1, results2):
                self.assertEqual(r1["status"], r2["status"],
                    f"Status mismatch for {r1['code']}: {r1['status']} vs {r2['status']}")
                self.assertEqual(r1["code"], r2["code"])

            all_statuses = {r["status"] for r in results1}
            self.assertEqual(all_statuses, {MISSING_SCRIPT_STATUS},
                f"All items without scripts should be {MISSING_SCRIPT_STATUS}, got {all_statuses}")

            self.assertIn("integrity_hash", report1["scan_info"])
            self.assertIn("integrity_hash", report2["scan_info"])
            self.assertEqual(
                report1["scan_info"]["integrity_hash"],
                report2["scan_info"]["integrity_hash"],
                "Two identical scans must produce identical integrity hashes",
            )

    def test_integrity_hash_different_for_different_results(self):
        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            script1 = self._create_dummy_script(td1, "check.ps1", "exit 0")
            script2 = self._create_dummy_script(td2, "check.ps1", "exit 1")

            item1 = self._make_item("1.1.1", script_path=script1)
            item2 = self._make_item("1.1.1", script_path=script2)

            report1 = self._run_scan_and_get_results([item1], td1)
            report2 = self._run_scan_and_get_results([item2], td2)

            hash1 = report1["scan_info"]["integrity_hash"]
            hash2 = report2["scan_info"]["integrity_hash"]

            self.assertNotEqual(hash1, hash2,
                "Different scan results must produce different integrity hashes")

    def test_items_with_scripts_produce_deterministic_results(self):
        with tempfile.TemporaryDirectory() as td:
            script = self._create_dummy_script(td, "check.ps1", "exit 0")

            with tempfile.TemporaryDirectory() as out1, tempfile.TemporaryDirectory() as out2:
                item = self._make_item("1.1.1", script_path=script)
                report1 = self._run_scan_and_get_results([item], out1)
                report2 = self._run_scan_and_get_results([item], out2)

                r1, r2 = report1["results"][0], report2["results"][0]
                self.assertEqual(r1["status"], r2["status"])
                self.assertEqual(r1["status"], PASS_STATUS)

    def test_scan_with_mixed_items_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            script = self._create_dummy_script(td, "good.ps1", "exit 0")

            items = [
                self._make_item("1.1.1", script_path=script),
                self._make_item("1.1.2"),
                self._make_item("1.1.3", script_path=script),
                self._make_item("1.1.4"),
            ]

            with tempfile.TemporaryDirectory() as out1, tempfile.TemporaryDirectory() as out2:
                report1 = self._run_scan_and_get_results(items, out1)
                report2 = self._run_scan_and_get_results(items, out2)

                results1 = {r["code"]: r["status"] for r in report1["results"]}
                results2 = {r["code"]: r["status"] for r in report2["results"]}

                self.assertEqual(results1, results2,
                    "Mixed items (with/without scripts) must produce deterministic results")

                self.assertEqual(results1["1.1.1"], PASS_STATUS)
                self.assertEqual(results1["1.1.2"], MISSING_SCRIPT_STATUS)
                self.assertEqual(results1["1.1.3"], PASS_STATUS)
                self.assertEqual(results1["1.1.4"], MISSING_SCRIPT_STATUS)

    def test_deterministic_results_across_three_consecutive_scans(self):
        items = [self._make_item(f"1.1.{i}") for i in range(1, 6)]

        with tempfile.TemporaryDirectory() as out1, \
             tempfile.TemporaryDirectory() as out2, \
             tempfile.TemporaryDirectory() as out3:

            report1 = self._run_scan_and_get_results(items, out1)
            report2 = self._run_scan_and_get_results(items, out2)
            report3 = self._run_scan_and_get_results(items, out3)

            h1 = report1["scan_info"]["integrity_hash"]
            h2 = report2["scan_info"]["integrity_hash"]
            h3 = report3["scan_info"]["integrity_hash"]

            self.assertEqual(h1, h2, "Scan 1 and 2 must have identical hashes")
            self.assertEqual(h2, h3, "Scan 2 and 3 must have identical hashes")

    def test_summary_counts_are_accurate(self):
        items = [
            self._make_item("1.1.1"),
            self._make_item("1.1.2"),
            self._make_item("1.1.3"),
        ]

        with tempfile.TemporaryDirectory() as td:
            report = self._run_scan_and_get_results(items, td)
            summary = report.get("scan_summary", {})

            self.assertEqual(summary.get("total"), 3)
            self.assertEqual(summary.get("pass"), 0)
            self.assertEqual(summary.get("fail"), 0)
            self.assertEqual(summary.get("script_missing"), 3)

    def test_actual_value_captured_from_script_output(self):
        with tempfile.TemporaryDirectory() as td:
            ps_content = 'Write-Output "actual: 24"'
            script = self._create_dummy_script(td, "check.ps1", ps_content)
            item = self._make_item("1.1.1", script_path=script)

            with tempfile.TemporaryDirectory() as out:
                report = self._run_scan_and_get_results([item], out)
                result = report["results"][0]
                self.assertEqual(result["status"], PASS_STATUS)
                self.assertIn("actual_value", result)
                self.assertIn("24", result["actual_value"])

    def test_expected_value_included_for_meaningful_results(self):
        with tempfile.TemporaryDirectory() as td:
            script = self._create_dummy_script(td, "check.ps1", "exit 0")
            item = self._make_item("1.1.1", script_path=script)

            with tempfile.TemporaryDirectory() as out:
                report = self._run_scan_and_get_results([item], out)
                result = report["results"][0]
                self.assertIn("expected_value", result)
                self.assertEqual(result["expected_value"], "expected_value")

    def test_scan_debug_log_contains_validation_info(self):
        with tempfile.TemporaryDirectory() as td:
            items = [self._make_item("1.1.1")]

            scanner = Scanner(items=items, output_dir=td)
            scanner.run()

            log_path = os.path.join(td, "scan_debug.log")
            self.assertTrue(os.path.exists(log_path))

            with open(log_path, "r", encoding="utf-8") as f:
                log_text = f.read()

            self.assertIn("scan_items_without_scripts", log_text)
            self.assertIn("scan_script_issues_detail", log_text)


if __name__ == "__main__":
    unittest.main()
