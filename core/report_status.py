PASS_STATUS = "Pass"
FAIL_STATUS = "Fail"
ERROR_STATUS = "Error"
UNSUPPORTED_STATUS = "Not Supported"
MISSING_SCRIPT_STATUS = "Script Missing"
SCRIPT_ERROR_STATUS = "Script Error"

_PASS_ALIASES = {
    "pass",
    "true",
    "yes",
    "1",
    "success",
    "ok",
    "compliant",
    "enabled",
}

_FAIL_ALIASES = {
    "fail",
    "false",
    "no",
    "0",
    "noncompliant",
    "disabled",
    "not configured",
}

_ERROR_ALIASES = {
    "error",
    "exception",
    "timeout",
    "script_error",
    "script_exception",
    "script_timeout",
    "runtime error",
}

_UNSUPPORTED_ALIASES = {
    "not support",
    "not supported",
    "not_support",
    "unsupported",
    "not applicable",
    "n/a",
    "not checked",
    "skipped",
}

_MISSING_SCRIPT_ALIASES = {
    "missing_script_path",
    "script_not_found",
    "no_script",
    "script missing",
}

_SCRIPT_ERROR_ALIASES = {
    "script_failed",
    "script_passed",
}

_STATUS_DIAGNOSTIC = {
    PASS_STATUS: "PASS_DIAGNOSTIC",
    FAIL_STATUS: "FAIL_DIAGNOSTIC",
    ERROR_STATUS: "ERROR_DIAGNOSTIC",
    UNSUPPORTED_STATUS: "UNSUPPORTED_DIAGNOSTIC",
    MISSING_SCRIPT_STATUS: "MISSING_SCRIPT_DIAGNOSTIC",
    SCRIPT_ERROR_STATUS: "SCRIPT_ERROR_DIAGNOSTIC",
}

def normalize_report_status(value):
    if value is None:
        return FAIL_STATUS

    text = str(value).strip()
    if not text:
        return FAIL_STATUS

    key = text.lower()

    if key in _PASS_ALIASES:
        return PASS_STATUS
    if key in _MISSING_SCRIPT_ALIASES:
        return MISSING_SCRIPT_STATUS
    if key in _UNSUPPORTED_ALIASES:
        return UNSUPPORTED_STATUS
    if key in _ERROR_ALIASES:
        return ERROR_STATUS
    if key in _SCRIPT_ERROR_ALIASES:
        return SCRIPT_ERROR_STATUS
    if key in _FAIL_ALIASES:
        return FAIL_STATUS

    if "pass" in key or "success" in key or "ok" in key:
        return PASS_STATUS
    if "error" in key or "exception" in key or "timeout" in key:
        return ERROR_STATUS
    if "support" in key:
        return UNSUPPORTED_STATUS
    if "missing" in key or "not_found" in key or "not found" in key:
        return MISSING_SCRIPT_STATUS

    return FAIL_STATUS


def normalize_report_data(report_data):
    data = report_data if isinstance(report_data, dict) else {}
    results = data.get("results")
    if not isinstance(results, list):
        data["results"] = []
        return data

    for item in results:
        if not isinstance(item, dict):
            continue
        item["status"] = normalize_report_status(item.get("status"))
        detail = item.get("detail", "")
        item["raw_detail"] = detail
        if detail and not item.get("status_detail"):
            item["status_detail"] = detail
    return data


def get_status_diagnostic_key(status):
    return _STATUS_DIAGNOSTIC.get(status, "FAIL_DIAGNOSTIC")


def is_infrastructure_error(status):
    return status in (MISSING_SCRIPT_STATUS, SCRIPT_ERROR_STATUS, ERROR_STATUS)


def is_meaningful_result(status):
    return status in (PASS_STATUS, FAIL_STATUS, UNSUPPORTED_STATUS)


_CONFIDENCE_EXACT_MATCH = 1.0
_CONFIDENCE_SUBSTRING_MATCH = 0.7
_CONFIDENCE_FALLBACK = 0.3
_CONFIDENCE_EMPTY_INPUT = 0.0

_AMBIGUOUS_KEYWORDS = [
    ("pass", _PASS_ALIASES),
    ("fail", _FAIL_ALIASES),
    ("error", _ERROR_ALIASES),
    ("support", _UNSUPPORTED_ALIASES),
    ("missing", _MISSING_SCRIPT_ALIASES),
    ("script", _SCRIPT_ERROR_ALIASES),
]


def get_status_confidence(value) -> float:
    if value is None:
        return _CONFIDENCE_EMPTY_INPUT

    text = str(value).strip()
    if not text:
        return _CONFIDENCE_EMPTY_INPUT

    key = text.lower()

    for alias_set in [_PASS_ALIASES, _FAIL_ALIASES, _ERROR_ALIASES,
                      _UNSUPPORTED_ALIASES, _MISSING_SCRIPT_ALIASES, _SCRIPT_ERROR_ALIASES]:
        if key in alias_set:
            return _CONFIDENCE_EXACT_MATCH

    matched_categories = 0
    for keyword, _ in _AMBIGUOUS_KEYWORDS:
        if keyword in key:
            matched_categories += 1

    if matched_categories == 0:
        return _CONFIDENCE_FALLBACK
    if matched_categories == 1:
        return _CONFIDENCE_SUBSTRING_MATCH
    return _CONFIDENCE_FALLBACK


def is_ambiguous_status(value) -> bool:
    if value is None:
        return False
    text = str(value).strip().lower()
    if not text:
        return False
    matches = sum(1 for kw, _ in _AMBIGUOUS_KEYWORDS if kw in text)
    return matches >= 2


def validate_status_detail_consistency(status: str, detail: str) -> bool:
    if not status or not detail:
        return True
    detail_lower = detail.lower()
    if status == PASS_STATUS and any(kw in detail_lower for kw in ("fail", "error", "noncompliant", "timeout")):
        return False
    if status == FAIL_STATUS and detail_lower not in ("noncompliant", "fail", "not configured", "disabled") and any(
        kw in detail_lower for kw in ("pass", "compliant", "success")
    ):
        return False
    return True


def sanitize_status_input(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if len(text) > 200:
        text = text[:200]
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    return text
