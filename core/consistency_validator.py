import re
import hashlib
from typing import List, Dict, Any

from core.hallucination_types import HallucinationIssue, HallucinationSeverity
from core.report_status import (
    PASS_STATUS,
    FAIL_STATUS,
    UNSUPPORTED_STATUS,
)


class ConsistencyValidator:
    def validate_all(
        self, results: List[Dict[str, Any]], report_data: Dict[str, Any]
    ) -> List[HallucinationIssue]:
        issues: List[HallucinationIssue] = []

        issues.extend(self._check_summary_consistency(results, report_data))
        issues.extend(self._check_duplicate_codes(results))
        issues.extend(self._check_hash_integrity(report_data))
        issues.extend(self._check_timestamp_consistency(results, report_data))
        issues.extend(self._check_unexpected_empty_results(results))
        issues.extend(self._check_status_count_anomalies(results))
        issues.extend(self._check_sequential_code_gaps(results))

        return issues

    def _check_summary_consistency(
        self, results: List[Dict[str, Any]], report_data: Dict[str, Any]
    ) -> List[HallucinationIssue]:
        summary = report_data.get("scan_summary")
        if not isinstance(summary, dict):
            return []

        issues: List[HallucinationIssue] = []
        total = len(results)
        declared_total = summary.get("total")
        if declared_total is not None and int(declared_total) != total:
            issues.append(HallucinationIssue(
                severity=HallucinationSeverity.HIGH,
                category="consistency",
                code="GLOBAL",
                field="scan_summary.total",
                message=f"Declared total ({declared_total}) != actual results count ({total})",
                actual_value=str(declared_total),
                expected_value=str(total),
                recommendation="Recalculate summary after results are finalized",
            ))

        actual_pass = sum(1 for r in results if r.get("status") == PASS_STATUS)
        declared_pass = summary.get("pass")
        if declared_pass is not None and int(declared_pass) != actual_pass:
            issues.append(HallucinationIssue(
                severity=HallucinationSeverity.HIGH,
                category="consistency",
                code="GLOBAL",
                field="scan_summary.pass",
                message=f"Declared pass ({declared_pass}) != actual pass count ({actual_pass})",
                actual_value=str(declared_pass),
                expected_value=str(actual_pass),
            ))

        actual_fail = sum(1 for r in results if r.get("status") == FAIL_STATUS)
        declared_fail = summary.get("fail")
        if declared_fail is not None and int(declared_fail) != actual_fail:
            issues.append(HallucinationIssue(
                severity=HallucinationSeverity.HIGH,
                category="consistency",
                code="GLOBAL",
                field="scan_summary.fail",
                message=f"Declared fail ({declared_fail}) != actual fail count ({actual_fail})",
                actual_value=str(declared_fail),
                expected_value=str(actual_fail),
            ))

        sum_breakdown = (summary.get("pass", 0) + summary.get("fail", 0) +
                         summary.get("script_missing", 0) + summary.get("error", 0))
        if declared_total is not None and sum_breakdown != declared_total:
            issues.append(HallucinationIssue(
                severity=HallucinationSeverity.MEDIUM,
                category="consistency",
                code="GLOBAL",
                field="scan_summary",
                message=f"Summary breakdown ({sum_breakdown}) does not sum to total ({declared_total})",
            ))

        return issues

    def _check_duplicate_codes(self, results: List[Dict[str, Any]]) -> List[HallucinationIssue]:
        seen: Dict[str, int] = {}
        for r in results:
            code = r.get("code", "")
            if not code:
                continue
            seen[code] = seen.get(code, 0) + 1

        issues: List[HallucinationIssue] = []
        for code, count in seen.items():
            if count > 1:
                issues.append(HallucinationIssue(
                    severity=HallucinationSeverity.HIGH,
                    category="consistency",
                    code=str(code),
                    field="code",
                    message=f"Duplicate result entry for code '{code}' appears {count} times",
                    recommendation="Ensure each CIS item is evaluated exactly once",
                ))
        return issues

    def _check_hash_integrity(self, report_data: Dict[str, Any]) -> List[HallucinationIssue]:
        scan_info = report_data.get("scan_info", {})
        if not isinstance(scan_info, dict):
            return []

        declared_hash = scan_info.get("integrity_hash")
        if not declared_hash:
            return [HallucinationIssue(
                severity=HallucinationSeverity.MEDIUM,
                category="consistency",
                code="GLOBAL",
                field="scan_info.integrity_hash",
                message="Integrity hash is missing from scan_info",
                recommendation="Ensure _compute_scan_hash runs before report is saved",
            )]

        if not re.match(r"^[a-f0-9]{64}$", str(declared_hash)):
            return [HallucinationIssue(
                severity=HallucinationSeverity.HIGH,
                category="consistency",
                code="GLOBAL",
                field="scan_info.integrity_hash",
                message=f"Integrity hash '{declared_hash}' is not a valid SHA-256 hex string",
                actual_value=str(declared_hash),
            )]

        results = report_data.get("results", [])
        if isinstance(results, list) and results:
            h = hashlib.sha256()
            for r in sorted(results, key=lambda x: x.get("code", "")):
                h.update(r.get("code", "").encode())
                h.update(r.get("status", "").encode())
                h.update(r.get("detail", "").encode())
            computed = h.hexdigest()
            if computed != declared_hash:
                return [HallucinationIssue(
                    severity=HallucinationSeverity.CRITICAL,
                    category="consistency",
                    code="GLOBAL",
                    field="scan_info.integrity_hash",
                    message="Integrity hash mismatch: results may have been tampered with",
                    actual_value=str(declared_hash)[:16] + "...",
                    expected_value=str(computed)[:16] + "...",
                    recommendation="Regenerate hash from current results",
                )]

        return []

    def _check_timestamp_consistency(
        self, results: List[Dict[str, Any]], report_data: Dict[str, Any]
    ) -> List[HallucinationIssue]:
        issues: List[HallucinationIssue] = []
        scan_info = report_data.get("scan_info", {})
        if not isinstance(scan_info, dict):
            return issues

        report_date = scan_info.get("date", "")
        for r in results:
            ts = r.get("timestamp", "")
            if ts and report_date:
                if not str(ts).startswith(str(report_date)):
                    issues.append(HallucinationIssue(
                        severity=HallucinationSeverity.LOW,
                        category="consistency",
                        code=str(r.get("code", "")),
                        field="timestamp",
                        message=f"Timestamp '{ts}' is inconsistent with report date '{report_date}'",
                    ))
                    break
        return issues

    def _check_unexpected_empty_results(self, results: List[Dict[str, Any]]) -> List[HallucinationIssue]:
        if results is None:
            return [HallucinationIssue(
                severity=HallucinationSeverity.CRITICAL,
                category="consistency",
                code="GLOBAL",
                field="results",
                message="Results list is None, expected at least an empty list",
            )]
        if len(results) == 0:
            return [HallucinationIssue(
                severity=HallucinationSeverity.MEDIUM,
                category="consistency",
                code="GLOBAL",
                field="results",
                message="Results list is empty: no items were scanned",
                recommendation="Check that scan items are selected and scripts are available",
            )]
        return []

    def _check_status_count_anomalies(self, results: List[Dict[str, Any]]) -> List[HallucinationIssue]:
        total = len(results)
        if total == 0:
            return []

        fail_count = sum(1 for r in results if r.get("status") == FAIL_STATUS)
        pass_count = sum(1 for r in results if r.get("status") == PASS_STATUS)
        unsupported_count = sum(1 for r in results if r.get("status") == UNSUPPORTED_STATUS)

        issues: List[HallucinationIssue] = []
        if total > 0 and fail_count == total and pass_count == 0:
            issues.append(HallucinationIssue(
                severity=HallucinationSeverity.MEDIUM,
                category="consistency",
                code="GLOBAL",
                field="status",
                message=f"All {total} items report Fail - this may indicate a systemic issue rather than all checks failing",
                recommendation="Verify scripts are executing correctly and returning properly formatted output",
            ))

        if unsupported_count > total * 0.5:
            issues.append(HallucinationIssue(
                severity=HallucinationSeverity.LOW,
                category="consistency",
                code="GLOBAL",
                field="status",
                message=f"{unsupported_count}/{total} items are Not Supported - verify OS matching",
            ))

        return issues

    def _check_sequential_code_gaps(self, results: List[Dict[str, Any]]) -> List[HallucinationIssue]:
        codes = sorted(
            [r.get("code", "") for r in results if r.get("code") and re.match(r"^\d+(?:\.\d+)+$", str(r.get("code", "")))],
            key=lambda c: tuple(int(x) for x in c.split(".")),
        )
        if len(codes) < 2:
            return []

        issues: List[HallucinationIssue] = []
        for i in range(len(codes) - 1):
            parts_a = [int(x) for x in codes[i].split(".")]
            parts_b = [int(x) for x in codes[i + 1].split(".")]
            if len(parts_a) != len(parts_b):
                continue
            if parts_a[0] != parts_b[0]:
                continue
            expected = parts_a[-1] + 1
            if parts_b[-1] > expected + 5:
                issues.append(HallucinationIssue(
                    severity=HallucinationSeverity.LOW,
                    category="consistency",
                    code="GLOBAL",
                    field="code",
                    message=f"Large gap between '{codes[i]}' and '{codes[i + 1]}' suggests missing items in scan results",
                ))
                break
        return issues
