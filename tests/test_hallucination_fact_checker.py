import unittest

from core.fact_checker import FactChecker
from core.hallucination_types import HallucinationSeverity


class TestFactChecker(unittest.TestCase):
    def setUp(self):
        self.checker = FactChecker()

    def _make_result(self, code, level="L1", status="Pass", description="Test desc",
                     suggestion="Set 'X' to 'Y'", detail="compliant",
                     actual_value=None):
        r = {
            "code": code,
            "level": level,
            "status": status,
            "description": description,
            "suggestion": suggestion,
            "detail": detail,
            "timestamp": "2026-01-01T00:00:00",
        }
        if actual_value is not None:
            r["actual_value"] = actual_value
        return r

    def test_empty_code_is_critical(self):
        r = self._make_result("")
        issues = self.checker.check_item(r)
        critical = [i for i in issues if i.severity == HallucinationSeverity.CRITICAL]
        self.assertGreaterEqual(len(critical), 1)
        self.assertIn("code", critical[0].field)

    def test_malformed_code_is_high(self):
        r = self._make_result("abc")
        issues = self.checker.check_item(r)
        high = [i for i in issues if i.severity == HallucinationSeverity.HIGH]
        self.assertGreaterEqual(len(high), 1)

    def test_valid_code_no_issue(self):
        r = self._make_result("1.1.1")
        issues = self.checker.check_item(r)
        code_issues = [i for i in issues if i.field == "code"]
        self.assertEqual(len(code_issues), 0)

    def test_empty_level_is_medium(self):
        r = self._make_result("1.1.1", level="")
        issues = self.checker.check_item(r)
        level_issues = [i for i in issues if i.field == "level"]
        self.assertGreaterEqual(len(level_issues), 1)

    def test_invalid_level_is_medium(self):
        r = self._make_result("1.1.1", level="L3")
        issues = self.checker.check_item(r)
        level_issues = [i for i in issues if i.field == "level"]
        self.assertGreaterEqual(len(level_issues), 1)

    def test_empty_status_is_critical(self):
        r = self._make_result("1.1.1", status="")
        issues = self.checker.check_item(r)
        status_issues = [i for i in issues if i.field == "status"]
        critical_status = [i for i in status_issues if i.severity == HallucinationSeverity.CRITICAL]
        self.assertGreaterEqual(len(critical_status), 1)

    def test_invalid_status_is_high(self):
        r = self._make_result("1.1.1", status="weird_status")
        issues = self.checker.check_item(r)
        status_issues = [i for i in issues if i.field == "status"]
        self.assertGreaterEqual(len(status_issues), 1)

    def test_empty_description_is_medium(self):
        r = self._make_result("1.1.1", description="")
        issues = self.checker.check_item(r)
        desc_issues = [i for i in issues if i.field == "description"]
        self.assertGreaterEqual(len(desc_issues), 1)

    def test_placeholder_description_is_medium(self):
        r = self._make_result("1.1.1", description="None")
        issues = self.checker.check_item(r)
        desc_issues = [i for i in issues if i.field == "description"]
        self.assertGreaterEqual(len(desc_issues), 1)

    def test_empty_suggestion_is_low(self):
        r = self._make_result("1.1.1", suggestion="")
        issues = self.checker.check_item(r)
        sug_issues = [i for i in issues if i.field == "suggestion"]
        self.assertGreaterEqual(len(sug_issues), 1)

    def test_short_suggestion_is_medium(self):
        r = self._make_result("1.1.1", suggestion="ab")
        issues = self.checker.check_item(r)
        sug_issues = [i for i in issues if i.field == "suggestion"]
        self.assertGreaterEqual(len(sug_issues), 1)

    def test_actual_value_containing_error_string_is_high(self):
        r = self._make_result("1.1.1", status="Pass", actual_value="Access Denied")
        issues = self.checker.check_item(r)
        actual_issues = [i for i in issues if i.field == "actual_value"]
        high = [i for i in actual_issues if i.severity == HallucinationSeverity.HIGH]
        self.assertGreaterEqual(len(high), 1)

    def test_actual_value_too_long_is_medium(self):
        r = self._make_result("1.1.1", status="Pass", actual_value="x" * 1200)
        issues = self.checker.check_item(r)
        actual_issues = [i for i in issues if i.field == "actual_value"]
        self.assertGreaterEqual(len(actual_issues), 1)

    def test_pass_without_actual_value_is_low(self):
        r = self._make_result("1.1.1", status="Pass", actual_value=None)
        issues = self.checker.check_item(r)
        actual_issues = [i for i in issues if i.field == "actual_value"]
        self.assertGreaterEqual(len(actual_issues), 1)

    def test_placeholder_detail_is_low(self):
        r = self._make_result("1.1.1", detail="None")
        issues = self.checker.check_item(r)
        detail_issues = [i for i in issues if i.field == "detail"]
        self.assertGreaterEqual(len(detail_issues), 1)

    def test_cross_validation_missing_result_code(self):
        results = [self._make_result("1.1.99")]
        items = [{"code": "1.1.1", "level": "L1", "description": "desc"}]
        issues = self.checker.check_cross_validity(results, items)
        self.assertTrue(any(i.field == "code" and "not match" in i.message for i in issues))

    def test_cross_validation_missing_item_in_results(self):
        results = [self._make_result("1.1.1")]
        items = [
            {"code": "1.1.1", "level": "L1", "description": "desc"},
            {"code": "1.1.2", "level": "L1", "description": "desc"}
        ]
        issues = self.checker.check_cross_validity(results, items)
        self.assertTrue(any("1.1.2" in i.message for i in issues))

    def test_cross_validation_level_mismatch(self):
        results = [self._make_result("1.1.1", level="L2")]
        items = [{"code": "1.1.1", "level": "L1", "description": "desc"}]
        issues = self.checker.check_cross_validity(results, items)
        level_issues = [i for i in issues if i.field == "level"]
        self.assertGreaterEqual(len(level_issues), 1)

    def test_clean_result_produces_no_fact_issues(self):
        r = self._make_result(
            "1.1.1",
            level="L1",
            status="Pass",
            description="Enforce password history is set to 24",
            suggestion="Set 'Enforce password history' to '24'",
            detail="compliant",
            actual_value="24",
        )
        r["timestamp"] = "2026-01-01T00:00:00"
        issues = self.checker.check_item(r)
        critical_or_high = [i for i in issues
                          if i.severity in (HallucinationSeverity.CRITICAL, HallucinationSeverity.HIGH)]
        self.assertEqual(len(critical_or_high), 0, f"Unexpected issues: {critical_or_high}")


if __name__ == "__main__":
    unittest.main()
