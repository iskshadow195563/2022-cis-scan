import unittest
import hashlib

from core.consistency_validator import ConsistencyValidator
from core.hallucination_types import HallucinationSeverity


class TestConsistencyValidator(unittest.TestCase):
    def setUp(self):
        self.validator = ConsistencyValidator()

    def _make_result(self, code, status="Pass", detail="compliant"):
        return {"code": code, "status": status, "detail": detail}

    def _make_report(self, results, summary_override=None):
        total = len(results)
        passed = sum(1 for r in results if r["status"] == "Pass")
        failed = sum(1 for r in results if r["status"] == "Fail")
        missing = sum(1 for r in results if r["status"] == "Script Missing")
        errors = sum(1 for r in results if r["status"] in ("Error", "Script Error"))

        scan_info = {
            "date": "2026-01-01",
            "time": "00:00:00",
        }

        if summary_override is not None:
            summary = summary_override
        else:
            summary = {
                "total": total,
                "pass": passed,
                "fail": failed,
                "script_missing": missing,
                "error": errors,
            }

        h = hashlib.sha256()
        for r in sorted(results, key=lambda x: x.get("code", "")):
            h.update(r.get("code", "").encode())
            h.update(r.get("status", "").encode())
            h.update(r.get("detail", "").encode())
        scan_info["integrity_hash"] = h.hexdigest()

        return {"scan_info": scan_info, "scan_summary": summary, "results": results}

    def test_summary_total_mismatch_is_high(self):
        results = [self._make_result("1.1.1", "Pass")]
        report = self._make_report(results, summary_override={"total": 99, "pass": 1, "fail": 0, "script_missing": 0, "error": 0})
        issues = self.validator.validate_all(results, report)
        total_issues = [i for i in issues if "total" in i.field]
        self.assertGreaterEqual(len(total_issues), 1)

    def test_summary_pass_count_mismatch_is_high(self):
        results = [self._make_result("1.1.1", "Pass")]
        report = self._make_report(results, summary_override={"total": 1, "pass": 99, "fail": 0, "script_missing": 0, "error": 0})
        issues = self.validator.validate_all(results, report)
        pass_issues = [i for i in issues if "pass" in i.field]
        self.assertGreaterEqual(len(pass_issues), 1)

    def test_duplicate_codes_are_high(self):
        results = [
            self._make_result("1.1.1", "Pass"),
            self._make_result("1.1.1", "Fail"),
        ]
        report = self._make_report(results)
        issues = self.validator.validate_all(results, report)
        dup_issues = [i for i in issues if "duplicate" in i.message.lower()]
        self.assertGreaterEqual(len(dup_issues), 1)

    def test_hash_tampering_is_critical(self):
        results = [self._make_result("1.1.1", "Pass")]
        report = self._make_report(results)
        report["scan_info"]["integrity_hash"] = "a" * 64
        issues = self.validator.validate_all(results, report)
        hash_issues = [i for i in issues if i.field == "scan_info.integrity_hash"
                       and i.severity == HallucinationSeverity.CRITICAL]
        self.assertGreaterEqual(len(hash_issues), 1)

    def test_missing_hash_is_medium(self):
        results = [self._make_result("1.1.1", "Pass")]
        report = self._make_report(results)
        del report["scan_info"]["integrity_hash"]
        issues = self.validator.validate_all(results, report)
        hash_issues = [i for i in issues if "integrity_hash" in i.field]
        self.assertGreaterEqual(len(hash_issues), 1)

    def test_empty_results_is_medium(self):
        report = self._make_report([], summary_override={"total": 0, "pass": 0, "fail": 0, "script_missing": 0, "error": 0})
        issues = self.validator.validate_all([], report)
        self.assertTrue(any("empty" in i.message.lower() for i in issues))

    def test_all_fail_is_medium_anomaly(self):
        results = [self._make_result(f"1.1.{i}", "Fail") for i in range(1, 6)]
        report = self._make_report(results)
        issues = self.validator.validate_all(results, report)
        anomaly_issues = [i for i in issues if "All" in i.message]
        self.assertGreaterEqual(len(anomaly_issues), 1)

    def test_clean_report_no_issues(self):
        results = [
            self._make_result("1.1.1", "Pass"),
            self._make_result("1.1.2", "Fail"),
            self._make_result("1.1.3", "Pass"),
        ]
        report = self._make_report(results)
        issues = self.validator.validate_all(results, report)
        critical_or_high = [i for i in issues
                          if i.severity in (HallucinationSeverity.CRITICAL, HallucinationSeverity.HIGH)]
        self.assertEqual(len(critical_or_high), 0, f"Unexpected critical/high: {critical_or_high}")

    def test_summary_breakdown_no_sum_to_total(self):
        results = [self._make_result("1.1.1", "Pass"), self._make_result("1.1.2", "Fail")]
        report = self._make_report(results, summary_override={
            "total": 10, "pass": 1, "fail": 1, "script_missing": 0, "error": 0
        })
        issues = self.validator.validate_all(results, report)
        breakdown_issues = [i for i in issues if "breakdown" in i.message.lower() or "does not sum" in i.message.lower()]
        self.assertGreaterEqual(len(breakdown_issues), 1)


if __name__ == "__main__":
    unittest.main()
