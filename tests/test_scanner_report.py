import glob
import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from core.scanner import Scanner, build_suggestion
from core.report_status import (
    ERROR_STATUS,
    MISSING_SCRIPT_STATUS,
)


class TestScannerReport(unittest.TestCase):
    def test_build_suggestion_uses_explicit_recommended_value(self):
        suggestion = build_suggestion(
            "18.9.25.8",
            "Ensure 'Post-authentication actions: Actions' -> ''Enabled: Reset the password and logoff the managed account' or higher'",
            setting_name="Post-authentication actions: Actions",
            recommended_value="'Enabled: Reset the password and logoff the managed account' or higher",
        )
        self.assertIn("Post-authentication actions: Actions", suggestion)
        self.assertIn("Reset the password and logoff the managed account", suggestion)
        self.assertNotIn("' -", suggestion)
        self.assertNotIn("> '", suggestion)

    def test_report_contains_nowtime(self):
        with tempfile.TemporaryDirectory() as td:
            s = Scanner(items=[], output_dir=td)
            s.run()
            reports = glob.glob(os.path.join(td, "report_*.json"))
            self.assertEqual(len(reports), 1)
            with open(reports[0], "r", encoding="utf-8") as f:
                data = json.load(f)
            scan_info = data.get("scan_info") or {}
            self.assertIn("nowtime", scan_info)
            self.assertTrue(scan_info["nowtime"])

    def test_timeout_is_reported_as_fail(self):
        with tempfile.TemporaryDirectory() as td:
            script_path = os.path.join(td, "check.ps1")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write("exit 0\n")

            item = {
                "code": "1.1.1",
                "level": "L1",
                "description": "desc",
                "script_path": script_path,
            }
            scanner = Scanner(items=[item], output_dir=td)

            with patch(
                "core.scanner.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="powershell", timeout=60),
            ):
                scanner.run()

            reports = glob.glob(os.path.join(td, "report_*.json"))
            self.assertEqual(len(reports), 1)
            with open(reports[0], "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["results"][0]["status"], ERROR_STATUS)
            self.assertEqual(data["results"][0]["detail"], "script_timeout")

    def test_missing_script_path_is_deterministic_fail(self):
        with tempfile.TemporaryDirectory() as td:
            item = {
                "code": "1.1.2",
                "level": "L1",
                "description": "desc",
            }
            scanner = Scanner(items=[item], output_dir=td)

            scanner.run()

            reports = glob.glob(os.path.join(td, "report_*.json"))
            self.assertEqual(len(reports), 1)
            with open(reports[0], "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(data["results"][0]["status"], MISSING_SCRIPT_STATUS)
            self.assertEqual(data["results"][0]["detail"], "missing_script_path")

    def test_json_status_from_script_controls_report_status(self):
        with tempfile.TemporaryDirectory() as td:
            script_path = os.path.join(td, "check.ps1")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write("exit 1\n")

            item = {
                "code": "1.1.1",
                "level": "L1",
                "description": "desc",
                "script_path": script_path,
            }

            def fake_run(cmd, **kwargs):
                return subprocess.CompletedProcess(
                    cmd,
                    1,
                    stdout='[CIS_DEBUG] noise\n{"Status":"ERROR","Detail":"mapping_missing","Actual":"raw"}\n',
                    stderr="",
                )

            scanner = Scanner(items=[item], output_dir=td, subprocess_run=fake_run)
            scanner.run()

            reports = glob.glob(os.path.join(td, "report_*.json"))
            with open(reports[0], "r", encoding="utf-8") as f:
                data = json.load(f)

            result = data["results"][0]
            self.assertEqual(result["status"], ERROR_STATUS)
            self.assertEqual(result["detail"], "mapping_missing")
            self.assertEqual(result["actual_value"], "raw")

    def test_repeat_runs_with_same_missing_script_are_stable(self):
        item = {
            "code": "1.1.3",
            "level": "L1",
            "description": "desc",
        }

        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            scanner1 = Scanner(items=[item], output_dir=td1)
            scanner2 = Scanner(items=[item], output_dir=td2)

            scanner1.run()
            scanner2.run()

            report1 = glob.glob(os.path.join(td1, "report_*.json"))[0]
            report2 = glob.glob(os.path.join(td2, "report_*.json"))[0]
            with open(report1, "r", encoding="utf-8") as f1:
                data1 = json.load(f1)
            with open(report2, "r", encoding="utf-8") as f2:
                data2 = json.load(f2)

            self.assertEqual(data1["results"][0]["status"], MISSING_SCRIPT_STATUS)
            self.assertEqual(data2["results"][0]["status"], MISSING_SCRIPT_STATUS)
            self.assertEqual(data1["results"][0]["detail"], data2["results"][0]["detail"])

    def test_scan_debug_log_records_decision_path(self):
        with tempfile.TemporaryDirectory() as td:
            item = {
                "code": "2.2.1",
                "level": "L1",
                "description": "desc",
            }
            scanner = Scanner(items=[item], output_dir=td)

            scanner.run()

            log_path = os.path.join(td, "scan_debug.log")
            self.assertTrue(os.path.exists(log_path))
            with open(log_path, "r", encoding="utf-8") as f:
                log_text = f.read()

            self.assertIn("scan_start", log_text)
            self.assertIn("missing_script_path", log_text)
            self.assertIn("result_recorded", log_text)
            self.assertIn("scan_complete", log_text)


if __name__ == "__main__":
    unittest.main()
