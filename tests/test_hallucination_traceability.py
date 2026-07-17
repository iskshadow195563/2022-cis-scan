import unittest

from core.traceability import TraceabilityTracker, SOURCE_ITEM, SOURCE_UNKNOWN
from core.hallucination_types import HallucinationSeverity


class TestTraceability(unittest.TestCase):
    def setUp(self):
        self.tracker = TraceabilityTracker()

    def test_fields_with_matching_item_have_correct_source(self):
        self.assertEqual(TraceabilityTracker.get_field_source("code", True), SOURCE_ITEM)
        self.assertEqual(TraceabilityTracker.get_field_source("level", True), SOURCE_ITEM)
        self.assertEqual(TraceabilityTracker.get_field_source("description", True), SOURCE_ITEM)

    def test_fields_without_item_have_unknown_source(self):
        self.assertEqual(TraceabilityTracker.get_field_source("code", False), SOURCE_UNKNOWN)

    def test_source_item_mismatch_description_triggers_issue(self):
        results = [
            {"code": "1.1.1", "level": "L1",
             "description": "Result description",
             "status": "Pass", "suggestion": "test",
             "detail": "compliant", "timestamp": "2026-01-01T00:00:00"}
        ]
        items = [
            {"code": "1.1.1", "level": "L1",
             "description": "Source description"}
        ]
        issues = self.tracker.trace_all(results, items)
        desc_issues = [i for i in issues if i.field == "description"]
        self.assertGreaterEqual(len(desc_issues), 1)

    def test_source_item_level_mismatch_triggers_issue(self):
        results = [
            {"code": "1.1.1", "level": "L2",
             "description": "desc",
             "status": "Pass", "suggestion": "test",
             "detail": "compliant", "timestamp": "2026-01-01T00:00:00"}
        ]
        items = [
            {"code": "1.1.1", "level": "L1", "description": "desc"}
        ]
        issues = self.tracker.trace_all(results, items)
        level_issues = [i for i in issues if i.field == "level"]
        self.assertGreaterEqual(len(level_issues), 1)

    def test_matching_items_no_issues(self):
        results = [
            {"code": "1.1.1", "level": "L1",
             "description": "Passwords must be at least 14 characters",
             "status": "Pass", "suggestion": "Configure password length",
             "detail": "compliant", "timestamp": "2026-01-01T00:00:00"}
        ]
        items = [
            {"code": "1.1.1", "level": "L1",
             "description": "Passwords must be at least 14 characters"}
        ]
        issues = self.tracker.trace_all(results, items)
        critical_or_high = [i for i in issues
                          if i.severity in (HallucinationSeverity.CRITICAL, HallucinationSeverity.HIGH)]
        self.assertEqual(len(critical_or_high), 0)

    def test_result_without_matching_item_does_not_crash(self):
        results = [
            {"code": "99.99.99", "level": "L1",
             "description": "Some description",
             "status": "Pass", "suggestion": "test",
             "detail": "compliant", "timestamp": "2026-01-01T00:00:00"}
        ]
        items = [
            {"code": "1.1.1", "level": "L1", "description": "desc"}
        ]
        issues = self.tracker.trace_all(results, items)
        self.assertIsInstance(issues, list)

    def test_normalize_removes_parenthesized_content(self):
        result = TraceabilityTracker._normalize_for_compare("Ensure 'Value' (Automated)")
        item = TraceabilityTracker._normalize_for_compare("Ensure 'Value' (MS only)")
        self.assertEqual(result, item)


if __name__ == "__main__":
    unittest.main()
