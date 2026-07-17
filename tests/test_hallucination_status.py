import unittest

from core.report_status import (
    normalize_report_status,
    get_status_confidence,
    is_ambiguous_status,
    validate_status_detail_consistency,
    sanitize_status_input,
    PASS_STATUS,
    FAIL_STATUS,
    ERROR_STATUS,
    UNSUPPORTED_STATUS,
    MISSING_SCRIPT_STATUS,
    SCRIPT_ERROR_STATUS,
)


class TestStatusConfidence(unittest.TestCase):
    def test_exact_match_confidence_is_1(self):
        self.assertEqual(get_status_confidence("pass"), 1.0)
        self.assertEqual(get_status_confidence("compliant"), 1.0)
        self.assertEqual(get_status_confidence("fail"), 1.0)
        self.assertEqual(get_status_confidence("error"), 1.0)
        self.assertEqual(get_status_confidence("script_timeout"), 1.0)

    def test_substring_match_confidence_is_0_7(self):
        self.assertEqual(get_status_confidence("something passed"), 0.7)
        self.assertEqual(get_status_confidence("error occurred"), 0.7)
        self.assertEqual(get_status_confidence("not supported here"), 0.7)
        self.assertEqual(get_status_confidence("no_script item"), 0.7)

    def test_fallback_confidence_is_0_3(self):
        self.assertEqual(get_status_confidence("xyz_unknown_value"), 0.3)

    def test_none_input_confidence_is_0(self):
        self.assertEqual(get_status_confidence(None), 0.0)

    def test_empty_input_confidence_is_0(self):
        self.assertEqual(get_status_confidence(""), 0.0)
        self.assertEqual(get_status_confidence("   "), 0.0)

    def test_ambiguous_keyword_returns_low_confidence(self):
        conf = get_status_confidence("pass and error")
        self.assertLess(conf, 0.7)

    def test_is_ambiguous_detects_multiple_categories(self):
        self.assertTrue(is_ambiguous_status("pass or fail"))
        self.assertTrue(is_ambiguous_status("error: script missing"))
        self.assertFalse(is_ambiguous_status("pass"))
        self.assertFalse(is_ambiguous_status("fail"))
        self.assertFalse(is_ambiguous_status(""))
        self.assertFalse(is_ambiguous_status(None))

    def test_validate_status_detail_consistency_pass_with_error_detail(self):
        self.assertFalse(validate_status_detail_consistency(PASS_STATUS, "script_error"))
        self.assertFalse(validate_status_detail_consistency(PASS_STATUS, "timeout"))

    def test_validate_status_detail_consistency_fail_with_pass_detail(self):
        self.assertFalse(validate_status_detail_consistency(FAIL_STATUS, "compliant"))
        self.assertFalse(validate_status_detail_consistency(FAIL_STATUS, "success"))

    def test_validate_status_detail_consistency_happy_path(self):
        self.assertTrue(validate_status_detail_consistency(PASS_STATUS, "compliant"))
        self.assertTrue(validate_status_detail_consistency(FAIL_STATUS, "noncompliant"))
        self.assertTrue(validate_status_detail_consistency("", ""))
        self.assertTrue(validate_status_detail_consistency(PASS_STATUS, ""))

    def test_sanitize_truncates_long_text(self):
        long_text = "x" * 500
        result = sanitize_status_input(long_text)
        self.assertEqual(len(result), 200)

    def test_sanitize_removes_newlines(self):
        result = sanitize_status_input("pass\nfail\terror")
        self.assertNotIn("\n", result)
        self.assertNotIn("\t", result)

    def test_normalize_preserves_known_statuses(self):
        self.assertEqual(normalize_report_status("pass"), PASS_STATUS)
        self.assertEqual(normalize_report_status("fail"), FAIL_STATUS)
        self.assertEqual(normalize_report_status("error"), ERROR_STATUS)
        self.assertEqual(normalize_report_status("not supported"), UNSUPPORTED_STATUS)
        self.assertEqual(normalize_report_status("script missing"), MISSING_SCRIPT_STATUS)
        self.assertEqual(normalize_report_status("script_failed"), SCRIPT_ERROR_STATUS)


if __name__ == "__main__":
    unittest.main()
