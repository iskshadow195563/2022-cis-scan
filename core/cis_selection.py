import difflib
import re


def normalize_query(query):
    text = (query or "").strip().lower()
    return " ".join(text.split())


def normalize_for_token_match(text):
    text = (text or "").lower()
    # Keep ascii letters/digits, CJK and dot; remove other separators
    text = re.sub(r"[^0-9a-z\u4e00-\u9fff.]+", " ", text)
    return " ".join(text.split())


def is_subsequence(needle, haystack):
    if not needle:
        return True
    idx = 0
    for ch in haystack:
        if idx < len(needle) and ch == needle[idx]:
            idx += 1
            if idx == len(needle):
                return True
    return False


def row_matches_query(row, query):
    q = normalize_query(query)
    if not q:
        return True
    haystack_raw = " ".join(
        [
            str(row.get("number", "")),
            str(row.get("level", "")),
            str(row.get("name", "")),
            str(row.get("assessment", "")),
        ]
    ).lower()
    if q in haystack_raw:
        return True

    q_norm = normalize_for_token_match(q)
    haystack = normalize_for_token_match(haystack_raw)
    if not q_norm or not haystack:
        return False

    if q_norm in haystack:
        return True

    compact_q = q_norm.replace(" ", "")
    compact_haystack = haystack.replace(" ", "")
    if compact_q and compact_q in compact_haystack:
        return True
    if compact_q and is_subsequence(compact_q, compact_haystack):
        return True

    q_tokens = q_norm.split()
    h_tokens = haystack.split()
    if all(any(qt in ht for ht in h_tokens) for qt in q_tokens):
        return True

    # Token-level fuzzy matching to handle small typos (e.g. autimated -> automated)
    if q_tokens and h_tokens:
        token_fuzzy_match = all(
            any(difflib.SequenceMatcher(None, qt, ht).ratio() >= 0.8 for ht in h_tokens)
            for qt in q_tokens
        )
        if token_fuzzy_match:
            return True

    ratio = difflib.SequenceMatcher(None, compact_q, compact_haystack).ratio()
    return ratio >= 0.72


def apply_bulk_selection(rows, selected_codes, query, select_state, level_filter=None):
    q = normalize_query(query)
    next_selected = set(selected_codes or set())

    for row in rows:
        if not row_matches_query(row, q):
            continue
        level = row.get("level")
        if level_filter is not None and level not in level_filter:
            continue
        code = row.get("code") or row.get("number")
        if not code:
            continue
        if select_state:
            next_selected.add(code)
        else:
            next_selected.discard(code)

    return next_selected
