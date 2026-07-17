import json
import os
import subprocess
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from core.scanner import Scanner
from core.report_status import (
    PASS_STATUS,
    FAIL_STATUS,
    ERROR_STATUS,
    MISSING_SCRIPT_STATUS,
    normalize_report_status,
)


def _make_json_stdout(status, actual=None, detail="compliant", code="1.1.2"):
    obj = {"Code": code, "Status": status, "Detail": detail}
    if actual is not None:
        obj["Actual"] = actual
    return json.dumps(obj)


class FakeCompletedProcess:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestPasswordPolicyValidation(unittest.TestCase):

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

    def _run_scan_with_mock(self, items, output_dir, subprocess_run):
        scanner = Scanner(
            items=items,
            output_dir=output_dir,
            subprocess_run=subprocess_run,
        )
        scanner.run()
        import glob
        reports = glob.glob(os.path.join(output_dir, "report_*.json"))
        with open(reports[0], "r", encoding="utf-8") as f:
            return json.load(f)

    def _scan_single(self, code, stdout, returncode=0):
        with tempfile.TemporaryDirectory() as td:
            script = self._create_dummy_script(td, f"check_{code.replace('.', '_')}.ps1")
            item = self._make_item(code, script_path=script)
            mock_run = MagicMock(return_value=FakeCompletedProcess(
                returncode=returncode,
                stdout=stdout,
            ))
            report = self._run_scan_with_mock([item], td, mock_run)
            return report["results"][0]

    def test_max_password_age_less_than_365_returns_pass(self):
        result = self._scan_single(
            "1.1.2",
            _make_json_stdout("PASS", actual=42, detail="compliant", code="1.1.2"),
            returncode=0,
        )
        self.assertEqual(result["status"], PASS_STATUS)
        self.assertEqual(result["detail"], "compliant")
        self.assertIn("42", result.get("actual_value", ""))

    def test_max_password_age_equal_to_364_returns_pass(self):
        result = self._scan_single(
            "1.1.2",
            _make_json_stdout("PASS", actual=364, detail="compliant", code="1.1.2"),
            returncode=0,
        )
        self.assertEqual(result["status"], PASS_STATUS)

    def test_max_password_age_equal_to_365_returns_fail(self):
        result = self._scan_single(
            "1.1.2",
            _make_json_stdout("FAIL", actual=365, detail="noncompliant", code="1.1.2"),
            returncode=1,
        )
        self.assertEqual(result["status"], FAIL_STATUS)
        self.assertEqual(result["detail"], "noncompliant")

    def test_max_password_age_greater_than_365_returns_fail(self):
        result = self._scan_single(
            "1.1.2",
            _make_json_stdout("FAIL", actual=400, detail="noncompliant", code="1.1.2"),
            returncode=1,
        )
        self.assertEqual(result["status"], FAIL_STATUS)

    def test_max_password_age_zero_returns_fail(self):
        result = self._scan_single(
            "1.1.2",
            _make_json_stdout("FAIL", actual=0, detail="noncompliant", code="1.1.2"),
            returncode=1,
        )
        self.assertEqual(result["status"], FAIL_STATUS)

    def test_max_password_age_negative_returns_fail(self):
        result = self._scan_single(
            "1.1.2",
            _make_json_stdout("FAIL", actual=-1, detail="noncompliant", code="1.1.2"),
            returncode=1,
        )
        self.assertEqual(result["status"], FAIL_STATUS)

    def test_min_password_age_greater_or_equal_1_returns_pass(self):
        result = self._scan_single(
            "1.1.3",
            _make_json_stdout("PASS", actual=1, detail="compliant", code="1.1.3"),
            returncode=0,
        )
        self.assertEqual(result["status"], PASS_STATUS)

    def test_min_password_age_zero_returns_fail(self):
        result = self._scan_single(
            "1.1.3",
            _make_json_stdout("FAIL", actual=0, detail="noncompliant", code="1.1.3"),
            returncode=1,
        )
        self.assertEqual(result["status"], FAIL_STATUS)

    def test_min_password_length_14_or_more_returns_pass(self):
        result = self._scan_single(
            "1.1.4",
            _make_json_stdout("PASS", actual=14, detail="compliant", code="1.1.4"),
            returncode=0,
        )
        self.assertEqual(result["status"], PASS_STATUS)

    def test_min_password_length_less_than_14_returns_fail(self):
        result = self._scan_single(
            "1.1.4",
            _make_json_stdout("FAIL", actual=8, detail="noncompliant", code="1.1.4"),
            returncode=1,
        )
        self.assertEqual(result["status"], FAIL_STATUS)

    def test_lockout_threshold_less_or_equal_5_returns_pass(self):
        result = self._scan_single(
            "1.2.2",
            _make_json_stdout("PASS", actual=3, detail="compliant", code="1.2.2"),
            returncode=0,
        )
        self.assertEqual(result["status"], PASS_STATUS)

    def test_lockout_threshold_greater_than_5_returns_fail(self):
        result = self._scan_single(
            "1.2.2",
            _make_json_stdout("FAIL", actual=10, detail="noncompliant", code="1.2.2"),
            returncode=1,
        )
        self.assertEqual(result["status"], FAIL_STATUS)

    def test_lockout_duration_greater_or_equal_15_returns_pass(self):
        result = self._scan_single(
            "1.2.1",
            _make_json_stdout("PASS", actual=30, detail="compliant", code="1.2.1"),
            returncode=0,
        )
        self.assertEqual(result["status"], PASS_STATUS)

    def test_lockout_duration_less_than_15_returns_fail(self):
        result = self._scan_single(
            "1.2.1",
            _make_json_stdout("FAIL", actual=5, detail="noncompliant", code="1.2.1"),
            returncode=1,
        )
        self.assertEqual(result["status"], FAIL_STATUS)

    def test_lockout_duration_zero_returns_fail(self):
        result = self._scan_single(
            "1.2.1",
            _make_json_stdout("FAIL", actual=0, detail="noncompliant", code="1.2.1"),
            returncode=1,
        )
        self.assertEqual(result["status"], FAIL_STATUS)

    def test_lockout_window_15_or_more_returns_pass(self):
        result = self._scan_single(
            "1.2.3",
            _make_json_stdout("PASS", actual=15, detail="compliant", code="1.2.3"),
            returncode=0,
        )
        self.assertEqual(result["status"], PASS_STATUS)

    def test_script_error_returns_error_status(self):
        result = self._scan_single(
            "1.1.2",
            _make_json_stdout("ERROR", detail="script_exception", code="1.1.2"),
            returncode=1,
        )
        self.assertEqual(result["status"], ERROR_STATUS)
        self.assertEqual(result["detail"], "script_exception")

    def test_missing_script_path_returns_missing_status(self):
        with tempfile.TemporaryDirectory() as td:
            item = self._make_item("1.1.2")
            scanner = Scanner(items=[item], output_dir=td)
            scanner.run()
            import glob
            reports = glob.glob(os.path.join(td, "report_*.json"))
            with open(reports[0], "r", encoding="utf-8") as f:
                data = json.load(f)
            result = data["results"][0]
            self.assertEqual(result["status"], MISSING_SCRIPT_STATUS)

    def test_parse_script_output_parses_json_actual_field(self):
        with tempfile.TemporaryDirectory() as td:
            script = self._create_dummy_script(td, "check.ps1")
            item = self._make_item("1.1.2", script_path=script)
            stdout = _make_json_stdout("PASS", actual=42, code="1.1.2")
            mock_run = MagicMock(return_value=FakeCompletedProcess(
                returncode=0,
                stdout=stdout,
            ))
            scanner = Scanner(
                items=[item],
                output_dir=td,
                subprocess_run=mock_run,
            )
            scanner.run()
            import glob
            reports = glob.glob(os.path.join(td, "report_*.json"))
            with open(reports[0], "r", encoding="utf-8") as f:
                data = json.load(f)
            result = data["results"][0]
            self.assertEqual(result["status"], PASS_STATUS)
            self.assertEqual(result["actual_value"], "42")

    def test_parse_script_output_falls_back_to_regex(self):
        with tempfile.TemporaryDirectory() as td:
            script = self._create_dummy_script(td, "check.ps1")
            item = self._make_item("1.1.2", script_path=script)
            stdout = "The actual value: 42 days"
            mock_run = MagicMock(return_value=FakeCompletedProcess(
                returncode=0,
                stdout=stdout,
            ))
            scanner = Scanner(
                items=[item],
                output_dir=td,
                subprocess_run=mock_run,
            )
            scanner.run()
            import glob
            reports = glob.glob(os.path.join(td, "report_*.json"))
            with open(reports[0], "r", encoding="utf-8") as f:
                data = json.load(f)
            result = data["results"][0]
            self.assertIn("42", result["actual_value"])

    def test_scan_debug_log_records_password_policy_decisions(self):
        with tempfile.TemporaryDirectory() as td:
            script = self._create_dummy_script(td, "check.ps1")
            item = self._make_item("1.1.2", script_path=script)
            stdout = _make_json_stdout("PASS", actual=42, code="1.1.2")
            mock_run = MagicMock(return_value=FakeCompletedProcess(
                returncode=0,
                stdout=stdout,
            ))
            scanner = Scanner(
                items=[item],
                output_dir=td,
                subprocess_run=mock_run,
            )
            scanner.run()

            log_path = os.path.join(td, "scan_debug.log")
            self.assertTrue(os.path.exists(log_path))
            with open(log_path, "r", encoding="utf-8") as f:
                log_text = f.read()

            self.assertIn("scan_start", log_text)
            self.assertIn("run_script_start", log_text)
            self.assertIn("run_script_done", log_text)
            self.assertIn("result_recorded", log_text)
            self.assertIn("scan_complete", log_text)


class TestPasswordPolicyMappingIntegrity(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.mapping_path = os.path.join(base_dir, "data", "cis_mapping.json")
        with open(cls.mapping_path, "r", encoding="utf-8") as f:
            cls.mapping = json.load(f)

    def test_all_net_accounts_compare_entries_have_key_and_compare_op(self):
        broken = []
        for code, entry in self.mapping.items():
            if entry.get("action") != "net_accounts_compare":
                continue
            if not entry.get("key") or not entry.get("compare_op"):
                broken.append(code)
        self.assertEqual(
            broken, [],
            f"net_accounts_compare entries missing key/compare_op: {broken}"
        )

    def test_all_secedit_system_access_entries_have_system_access(self):
        broken = []
        for code, entry in self.mapping.items():
            if entry.get("action") != "secedit_system_access":
                continue
            if not entry.get("system_access"):
                broken.append(code)
        self.assertEqual(
            broken, [],
            f"secedit_system_access entries missing system_access: {broken}"
        )

    def test_password_policy_codes_exist_in_mapping(self):
        required = ["1.1.1", "1.1.2", "1.1.3", "1.1.4", "1.1.5", "1.1.6", "1.1.7"]
        missing = [c for c in required if c not in self.mapping]
        self.assertEqual(missing, [], f"Missing password policy codes: {missing}")

    def test_lockout_policy_codes_exist_in_mapping(self):
        required = ["1.2.1", "1.2.2", "1.2.3", "1.2.4"]
        missing = [c for c in required if c not in self.mapping]
        self.assertEqual(missing, [], f"Missing lockout policy codes: {missing}")

    def test_lockout_window_mapped_to_1_2_3_not_1_2_4(self):
        entry_123 = self.mapping.get("1.2.3", {})
        entry_124 = self.mapping.get("1.2.4", {})
        self.assertEqual(entry_123.get("key"), "LockoutWindow",
            "1.2.3 should have LockoutWindow key")
        self.assertNotEqual(entry_124.get("key"), "LockoutWindow",
            "1.2.4 should NOT have LockoutWindow key (belongs to 1.2.3)")

    def test_max_password_age_has_correct_compare_op(self):
        entry = self.mapping.get("1.1.2", {})
        self.assertEqual(entry.get("compare_op"), "le")
        self.assertEqual(entry.get("expected"), 365)
        self.assertEqual(entry.get("key"), "MaxPasswordAge")

    def test_min_password_length_has_correct_compare_op(self):
        entry = self.mapping.get("1.1.4", {})
        self.assertEqual(entry.get("compare_op"), "ge")
        self.assertEqual(entry.get("expected"), 14)
        self.assertEqual(entry.get("key"), "MinPasswordLength")


class TestNormalizeReportStatusEdgeCases(unittest.TestCase):

    def test_value_not_found_normalizes_to_fail(self):
        result = normalize_report_status("value_not_found")
        self.assertEqual(result, MISSING_SCRIPT_STATUS,
            "'value_not_found' contains 'not_found' → MISSING_SCRIPT_STATUS")

    def test_unknown_status_defaults_to_fail(self):
        result = normalize_report_status("some_unknown_status")
        self.assertEqual(result, FAIL_STATUS)

    def test_numeric_status_is_handled(self):
        result = normalize_report_status(0)
        self.assertEqual(result, FAIL_STATUS)

    def test_boolean_false_status(self):
        result = normalize_report_status(False)
        self.assertEqual(result, FAIL_STATUS)


if __name__ == "__main__":
    unittest.main()
