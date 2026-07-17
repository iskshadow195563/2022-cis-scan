import unittest

from core.report_compare import build_comparison_rows


class TestReportCompare(unittest.TestCase):
    def test_build_rows_handles_missing_values(self):
        prev = {"results": [{"code": "1.1.1", "description": None, "status": None}]}
        cur = {"results": [{"code": "1.1.1", "description": "Rule A", "status": "Pass"}]}
        rows = build_comparison_rows(prev, cur)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Rule A")
        self.assertEqual(rows[0]["old_status"], "Fail")
        self.assertEqual(rows[0]["new_status"], "Pass")

    def test_build_rows_includes_removed_items(self):
        prev = {"results": [{"code": "2.2.2", "description": "Rule B", "status": "Fail"}]}
        cur = {"results": []}
        rows = build_comparison_rows(prev, cur)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["name"], "Rule B")
        self.assertEqual(rows[0]["old_status"], "Fail")
        self.assertIsNone(rows[0]["new_status"])
        self.assertTrue(rows[0]["changed"])

    def test_build_rows_collapses_legacy_statuses_to_fail(self):
        prev = {"results": [{"code": "3.3.3", "description": "Rule C", "status": "Error"}]}
        cur = {"results": [{"code": "3.3.3", "description": "Rule C", "status": "Not Supported"}]}
        rows = build_comparison_rows(prev, cur)
        self.assertEqual(rows[0]["old_status"], "Error")
        self.assertEqual(rows[0]["new_status"], "Not Supported")
        self.assertTrue(rows[0]["changed"])

    def test_build_rows_preserves_status_details_and_values(self):
        prev = {
            "results": [
                {
                    "code": "4.4.4",
                    "description": "Rule D",
                    "status": "Error",
                    "detail": "script_timeout",
                    "actual_value": "timeout",
                }
            ]
        }
        cur = {
            "results": [
                {
                    "code": "4.4.4",
                    "description": "Rule D",
                    "status": "Not Supported",
                    "status_detail": "mapping_missing",
                    "expected_value": "Enabled",
                }
            ]
        }
        rows = build_comparison_rows(prev, cur)
        self.assertEqual(rows[0]["old_detail"], "script_timeout")
        self.assertEqual(rows[0]["old_actual_value"], "timeout")
        self.assertEqual(rows[0]["new_detail"], "mapping_missing")
        self.assertEqual(rows[0]["new_expected_value"], "Enabled")


if __name__ == "__main__":
    unittest.main()
