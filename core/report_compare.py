from core.report_status import normalize_report_status


def _normalize_status(value):
    return normalize_report_status(value)


def _normalize_name(value):
    if value is None:
        return ""
    return str(value).strip()


def _result_snapshot(result):
    code = _normalize_name(result.get("code"))
    detail = (
        _normalize_name(result.get("status_detail"))
        or _normalize_name(result.get("detail"))
        or _normalize_name(result.get("raw_detail"))
    )
    return {
        "code": code,
        "name": _normalize_name(result.get("description")) or code,
        "status": _normalize_status(result.get("status")),
        "detail": detail,
        "actual_value": _normalize_name(result.get("actual_value")),
        "expected_value": _normalize_name(result.get("expected_value")),
    }


def build_comparison_rows(prev_data, current_data):
    prev_results_list = (prev_data or {}).get("results") or []
    current_results_list = (current_data or {}).get("results") or []

    prev_by_code = {}
    for r in prev_results_list:
        if not isinstance(r, dict):
            continue
        code = _normalize_name(r.get("code"))
        if not code:
            continue
        prev_by_code[code] = _result_snapshot(r)

    current_by_code = {}
    for r in current_results_list:
        if not isinstance(r, dict):
            continue
        code = _normalize_name(r.get("code"))
        if not code:
            continue
        current_by_code[code] = _result_snapshot(r)

    codes = sorted(set(prev_by_code.keys()) | set(current_by_code.keys()))
    rows = []
    for code in codes:
        prev_item = prev_by_code.get(code)
        cur_item = current_by_code.get(code)
        name = (cur_item or prev_item or {}).get("name") or code
        old_status = (prev_item or {}).get("status")
        new_status = (cur_item or {}).get("status")
        changed = prev_item is None or cur_item is None or old_status != new_status
        rows.append(
            {
                "code": code,
                "name": name,
                "old_status": old_status,
                "new_status": new_status,
                "old_detail": (prev_item or {}).get("detail", ""),
                "new_detail": (cur_item or {}).get("detail", ""),
                "old_actual_value": (prev_item or {}).get("actual_value", ""),
                "new_actual_value": (cur_item or {}).get("actual_value", ""),
                "old_expected_value": (prev_item or {}).get("expected_value", ""),
                "new_expected_value": (cur_item or {}).get("expected_value", ""),
                "changed": changed,
            }
        )
    return rows
