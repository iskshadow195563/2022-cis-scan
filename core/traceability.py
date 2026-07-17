import re
from typing import List, Dict, Any, Optional

from core.hallucination_types import HallucinationIssue, HallucinationSeverity

SOURCE_SCRIPT = "script_output"
SOURCE_PARSER = "cis_parser"
SOURCE_COMPUTED = "computed"
SOURCE_DEFAULT = "default"
SOURCE_ITEM = "input_item"
SOURCE_UNKNOWN = "unknown"

SUGGESTION_SOURCE_PREFIX = {
    "Set '": "computed_from_code_and_item_fields",
    "Configure '": "computed_from_code_and_item_fields",
    "在": "computed_from_code_and_item_fields",
    "依 CIS": "computed_from_code_and_item_fields",
}


class TraceabilityTracker:
    def trace_all(
        self, results: List[Dict[str, Any]], items: List[Dict[str, Any]]
    ) -> List[HallucinationIssue]:
        issues: List[HallucinationIssue] = []
        item_by_code: Dict[str, Dict[str, Any]] = {}
        for item in items:
            code = item.get("code", "")
            if code:
                item_by_code[code] = item

        for result in results:
            if not isinstance(result, dict):
                continue
            code = result.get("code", "")
            item = item_by_code.get(code) if code else None
            issues.extend(self._trace_single_result(result, item))

        return issues

    def _trace_single_result(
        self, result: Dict[str, Any], item: Optional[Dict[str, Any]]
    ) -> List[HallucinationIssue]:
        issues: List[HallucinationIssue] = []
        code = result.get("code", "")

        lineage = {}
        if item:
            lineage["code"] = SOURCE_ITEM
            lineage["level"] = SOURCE_ITEM
            lineage["description"] = SOURCE_ITEM
            lineage["name"] = SOURCE_ITEM
            lineage["recommended"] = SOURCE_ITEM
        else:
            lineage["code"] = SOURCE_UNKNOWN
            lineage["level"] = SOURCE_UNKNOWN
            lineage["description"] = SOURCE_UNKNOWN

        lineage["status"] = SOURCE_SCRIPT
        lineage["actual_value"] = SOURCE_SCRIPT
        lineage["detail"] = SOURCE_SCRIPT
        lineage["suggestion"] = SOURCE_COMPUTED
        lineage["timestamp"] = SOURCE_COMPUTED

        for field, source in lineage.items():
            if source == SOURCE_UNKNOWN:
                value = result.get(field)
                if value is not None and str(value).strip():
                    pass
                elif field in ("code", "status", "description"):
                    issues.append(HallucinationIssue(
                        severity=HallucinationSeverity.MEDIUM,
                        category="traceability",
                        code=str(code),
                        field=field,
                        message=f"Field '{field}' has unknown source: no input item matched",
                        source=SOURCE_UNKNOWN,
                        recommendation="Ensure result entries reference valid CIS benchmark items",
                    ))

        issues.extend(self._cross_check_result_vs_item(result, item, str(code)))

        return issues

    def _cross_check_result_vs_item(
        self, result: Dict[str, Any], item: Optional[Dict[str, Any]], code: str
    ) -> List[HallucinationIssue]:
        issues: List[HallucinationIssue] = []

        if not item:
            return issues

        result_desc = result.get("description", "")
        item_desc = item.get("description", "")
        if result_desc and item_desc:
            result_desc_norm = self._normalize_for_compare(str(result_desc))
            item_desc_norm = self._normalize_for_compare(str(item_desc))
            if result_desc_norm and item_desc_norm:
                if result_desc_norm != item_desc_norm:
                    issues.append(HallucinationIssue(
                        severity=HallucinationSeverity.LOW,
                        category="traceability",
                        code=code,
                        field="description",
                        message="Result description differs from source item description",
                        actual_value=result_desc_norm[:120],
                        expected_value=item_desc_norm[:120],
                        source=SOURCE_ITEM,
                    ))

        result_level = result.get("level", "")
        item_level = item.get("level", "")
        if result_level and item_level:
            if str(result_level).strip() != str(item_level).strip():
                issues.append(HallucinationIssue(
                    severity=HallucinationSeverity.MEDIUM,
                    category="traceability",
                    code=code,
                    field="level",
                    message="Result level differs from source item level",
                    actual_value=str(result_level),
                    expected_value=str(item_level),
                    source=SOURCE_ITEM,
                ))

        return issues

    @staticmethod
    def _normalize_for_compare(text: str) -> str:
        cleaned = re.sub(r"\s+", " ", text).strip().lower()
        cleaned = re.sub(r"\s*\([^()]*\)\s*", "", cleaned)
        return cleaned

    @staticmethod
    def get_field_source(field: str, has_item: bool) -> str:
        sources = {
            "code": SOURCE_ITEM if has_item else SOURCE_UNKNOWN,
            "level": SOURCE_ITEM if has_item else SOURCE_UNKNOWN,
            "description": SOURCE_ITEM if has_item else SOURCE_UNKNOWN,
            "status": SOURCE_SCRIPT,
            "actual_value": SOURCE_SCRIPT,
            "detail": SOURCE_SCRIPT,
            "suggestion": SOURCE_COMPUTED,
            "timestamp": SOURCE_COMPUTED,
            "expected_value": SOURCE_ITEM if has_item else SOURCE_COMPUTED,
        }
        return sources.get(field, SOURCE_UNKNOWN)
