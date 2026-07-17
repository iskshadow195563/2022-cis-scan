import re
import json
from typing import List, Dict, Any, Optional

from core.hallucination_types import HallucinationIssue, HallucinationSeverity

CODE_PATTERN = re.compile(r"^\d+(?:\.\d+)+$")
LEVEL_PATTERN = re.compile(r"^L[12]$")
STATUS_PATTERN = re.compile(r"^(Pass|Fail|Error|Not Supported|Script Missing|Script Error)$")
KNOWN_SUGGESTION_PREFIXES = [
    "Set '",
    "Configure '",
    "在",
    "依 CIS",
]


class FactChecker:
    def check_all(
        self, results: List[Dict[str, Any]], items: Optional[List[Dict[str, Any]]] = None
    ) -> List[HallucinationIssue]:
        issues: List[HallucinationIssue] = []
        for result in results:
            if not isinstance(result, dict):
                continue
            issues.extend(self.check_item(result))
        if items:
            issues.extend(self.check_cross_validity(results, items))
        return issues

    def check_item(self, result: Dict[str, Any]) -> List[HallucinationIssue]:
        issues: List[HallucinationIssue] = []
        code = result.get("code", "")

        issues.extend(self._check_code_validity(code))
        issues.extend(self._check_level_validity(result, code))
        issues.extend(self._check_status_validity(result, code))
        issues.extend(self._check_description_integrity(result, code))
        issues.extend(self._check_suggestion_integrity(result, code))
        issues.extend(self._check_actual_value_plausibility(result, code))
        issues.extend(self._check_key_field_integrity(result, code))

        return issues

    def _check_code_validity(self, code: str) -> List[HallucinationIssue]:
        issues: List[HallucinationIssue] = []
        if not code:
            issues.append(HallucinationIssue(
                severity=HallucinationSeverity.CRITICAL,
                category="fact_check",
                code="UNKNOWN",
                field="code",
                message="Item code is empty or missing",
                recommendation="Verify CIS benchmark data source integrity",
            ))
        elif not CODE_PATTERN.match(str(code)):
            issues.append(HallucinationIssue(
                severity=HallucinationSeverity.HIGH,
                category="fact_check",
                code=str(code),
                field="code",
                message=f"Item code '{code}' does not match expected format (e.g. 1.1.1)",
                actual_value=str(code),
                recommendation="Check parser output for malformed item codes",
            ))
        return issues

    def _check_level_validity(self, result: Dict[str, Any], code: str) -> List[HallucinationIssue]:
        level = result.get("level", "")
        if not level:
            return [HallucinationIssue(
                severity=HallucinationSeverity.MEDIUM,
                category="fact_check",
                code=str(code),
                field="level",
                message="Level field is empty",
                recommendation="Verify item metadata from CIS benchmark source",
            )]
        if not LEVEL_PATTERN.match(str(level)):
            return [HallucinationIssue(
                severity=HallucinationSeverity.MEDIUM,
                category="fact_check",
                code=str(code),
                field="level",
                message=f"Level '{level}' is not a recognized CIS level (L1/L2)",
                actual_value=str(level),
                recommendation="Check benchmark parsing for level extraction",
            )]
        if str(code) and not str(code).startswith("2") and level == "L2" and not str(code).startswith("18") and not str(code).startswith("19"):
            pass
        return []

    def _check_status_validity(self, result: Dict[str, Any], code: str) -> List[HallucinationIssue]:
        status = result.get("status", "")
        if not status:
            return [HallucinationIssue(
                severity=HallucinationSeverity.CRITICAL,
                category="fact_check",
                code=str(code),
                field="status",
                message="Status field is empty",
                recommendation="Ensure every scan result has a status assigned",
            )]
        if not STATUS_PATTERN.match(str(status)):
            return [HallucinationIssue(
                severity=HallucinationSeverity.HIGH,
                category="fact_check",
                code=str(code),
                field="status",
                message=f"Status '{status}' is not a recognized status value",
                actual_value=str(status),
                recommendation="Check report_status.normalize_report_status output",
            )]
        return []

    def _check_description_integrity(self, result: Dict[str, Any], code: str) -> List[HallucinationIssue]:
        description = result.get("description", "")
        if not description:
            return [HallucinationIssue(
                severity=HallucinationSeverity.MEDIUM,
                category="fact_check",
                code=str(code),
                field="description",
                message="Description field is empty",
                recommendation="Verify item description is loaded from CIS benchmark data",
            )]
        desc_str = str(description)
        if desc_str.strip() in ("None", "null", "undefined", "N/A"):
            return [HallucinationIssue(
                severity=HallucinationSeverity.MEDIUM,
                category="fact_check",
                code=str(code),
                field="description",
                message=f"Description contains placeholder value '{desc_str}'",
                actual_value=desc_str,
                recommendation="Check data source for missing descriptions",
            )]
        suspicious_patterns = [
            (r"^\s*ensure\s+", "Description still has 'ensure' prefix (not normalized)"),
            (r"^\s*確保\s+", "Description still has '確保' prefix (not normalized)"),
        ]
        for pattern, msg in suspicious_patterns:
            if re.search(pattern, desc_str):
                issues = [HallucinationIssue(
                    severity=HallucinationSeverity.LOW,
                    category="fact_check",
                    code=str(code),
                    field="description",
                    message=msg,
                )]
                return issues
        return []

    def _check_suggestion_integrity(self, result: Dict[str, Any], code: str) -> List[HallucinationIssue]:
        suggestion = result.get("suggestion", "")
        if not suggestion:
            return [HallucinationIssue(
                severity=HallucinationSeverity.LOW,
                category="fact_check",
                code=str(code),
                field="suggestion",
                message="Suggestion field is empty",
            )]
        if len(str(suggestion)) < 5:
            return [HallucinationIssue(
                severity=HallucinationSeverity.MEDIUM,
                category="fact_check",
                code=str(code),
                field="suggestion",
                message=f"Suggestion is too short: '{suggestion}'",
                actual_value=str(suggestion),
            )]
        if str(suggestion).strip().endswith("。") and "。" not in str(suggestion).strip()[:-1]:
            return []
        return []

    def _check_actual_value_plausibility(self, result: Dict[str, Any], code: str) -> List[HallucinationIssue]:
        actual_value = result.get("actual_value")
        status = result.get("status", "")

        if actual_value is not None:
            av_str = str(actual_value)
            if isinstance(actual_value, str) and len(av_str) > 1000:
                return [HallucinationIssue(
                    severity=HallucinationSeverity.MEDIUM,
                    category="fact_check",
                    code=str(code),
                    field="actual_value",
                    message=f"Actual value is unusually long ({len(av_str)} chars)",
                    actual_value=av_str[:200] + "...",
                    recommendation="Check script output for unexpected large content",
                )]

        if status in ("Pass", "Fail") and actual_value is None:
            return [HallucinationIssue(
                severity=HallucinationSeverity.LOW,
                category="fact_check",
                code=str(code),
                field="actual_value",
                message=f"Meaningful status '{status}' but no actual_value captured",
                recommendation="Ensure script output provides actual configuration values",
            )]

        if actual_value is not None and isinstance(actual_value, str):
            bounce_patterns = [
                r"^error\b",
                r"^exception\b",
                r"access\s*denied",
                r"permission\s*denied",
            ]
            for pattern in bounce_patterns:
                if re.search(pattern, av_str, re.IGNORECASE):
                    return [HallucinationIssue(
                        severity=HallucinationSeverity.HIGH,
                        category="fact_check",
                        code=str(code),
                        field="actual_value",
                        message=f"Actual value may contain an error message: '{av_str[:100]}'",
                        actual_value=av_str,
                        recommendation="Verify script ran correctly, not returning error text as data",
                    )]

        return []

    def _check_key_field_integrity(self, result: Dict[str, Any], code: str) -> List[HallucinationIssue]:
        issues: List[HallucinationIssue] = []

        detail = result.get("detail", "")
        if isinstance(detail, str) and detail.strip().lower() in ("none", "null"):
            issues.append(HallucinationIssue(
                severity=HallucinationSeverity.LOW,
                category="fact_check",
                code=str(code),
                field="detail",
                message=f"Detail field contains '{detail}' placeholder",
            ))

        timestamp = result.get("timestamp", "")
        if not timestamp:
            issues.append(HallucinationIssue(
                severity=HallucinationSeverity.LOW,
                category="fact_check",
                code=str(code),
                field="timestamp",
                message="Timestamp is missing from result entry",
            ))

        return issues

    def check_cross_validity(
        self, results: List[Dict[str, Any]], items: List[Dict[str, Any]]
    ) -> List[HallucinationIssue]:
        issues: List[HallucinationIssue] = []
        item_codes = {item.get("code", "") for item in items if item.get("code")}
        result_codes = {r.get("code", "") for r in results if r.get("code")}

        for r in results:
            code = r.get("code", "")
            if not code:
                continue
            if code not in item_codes:
                issues.append(HallucinationIssue(
                    severity=HallucinationSeverity.HIGH,
                    category="cross_validation",
                    code=str(code),
                    field="code",
                    message=f"Result code '{code}' does not match any input item",
                    recommendation="Check scanner item mapping and result generation logic",
                ))

        for item in items:
            code = item.get("code", "")
            if not code:
                continue
            if code not in result_codes:
                issues.append(HallucinationIssue(
                    severity=HallucinationSeverity.HIGH,
                    category="cross_validation",
                    code=str(code),
                    field="code",
                    message=f"Input item '{code}' is missing from scan results",
                    recommendation="Check scan cancellation or early termination",
                ))

        item_by_code = {item.get("code", ""): item for item in items if item.get("code")}
        for r in results:
            code = r.get("code", "")
            if not code or code not in item_by_code:
                continue
            item = item_by_code[code]
            result_level = r.get("level", "")
            item_level = item.get("level", "")
            if result_level and item_level and result_level != item_level:
                issues.append(HallucinationIssue(
                    severity=HallucinationSeverity.MEDIUM,
                    category="cross_validation",
                    code=str(code),
                    field="level",
                    message=f"Level mismatch: result='{result_level}', item='{item_level}'",
                    actual_value=str(result_level),
                    expected_value=str(item_level),
                    recommendation="Verify level propagation from input items to results",
                ))

        return issues
