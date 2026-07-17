import re
import json
import os
from typing import List, Dict, Any, Optional

SECTION_RE = re.compile(r"^(\d+(?:\.\d+)*)\s+(.+)$")
ITEM_START_RE = re.compile(r"^\d+(?:\.\d+)+\s+\((L[12])\)\s+(Ensure|Configure)\b", re.IGNORECASE)
ITEM_PREFIX_RE = re.compile(r"^(?P<code>\d+(?:\.\d+)+)\s+\((?P<level>L[12])\)\s+(?P<verb>Ensure|Configure)\s+(?P<rest>.+)$", re.IGNORECASE)
PAGE_RE = re.compile(r"^Page\s+\d+\s*$", re.IGNORECASE)
PAGE_SUFFIX_RE = re.compile(r"\s+\.{2,}\s*\d+\s*$|\s+\d+\s*$")
TAG_RE = re.compile(r"\(([^()]*)\)")
VALUE_MARKER_RE = re.compile(r"\s+(is\s+set\s+to|to\s+include|is|be)\s+", re.IGNORECASE)
TRAILING_TAGS_RE = re.compile(r"(?:\s*\([^()]*\))+\s*$")

def _normalize_text(text: str) -> str:
    return " ".join((text or "").split()).strip()

def _strip_page_suffix(text: str) -> str:
    return PAGE_SUFFIX_RE.sub("", _normalize_text(text)).strip()

def _extract_tags(text: str) -> List[str]:
    return [_normalize_text(match) for match in TAG_RE.findall(text or "") if _normalize_text(match)]

def _strip_outer_quotes(text: str) -> str:
    value = (text or "").strip()
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].strip()
    return value

def _parse_item_record(text: str) -> Optional[Dict[str, Any]]:
    cleaned = _strip_page_suffix(text)
    match = ITEM_PREFIX_RE.match(cleaned)
    if not match:
        return None

    rest = match.group("rest").strip()
    tag_match = re.search(r"((?:\s*\([^()]*\))+)\s*$", rest)
    tag_blob = tag_match.group(1) if tag_match else ""
    content = rest[:tag_match.start()].strip() if tag_match else rest
    marker_match = VALUE_MARKER_RE.search(content)

    if marker_match:
        name = _strip_outer_quotes(content[:marker_match.start()].strip())
        recommended = _strip_outer_quotes(content[marker_match.end():].strip())
    else:
        name = _strip_outer_quotes(content)
        recommended = ""

    verb = match.group("verb")
    assessment_tags = _extract_tags(tag_blob)
    description = f"{verb} '{name}' -> '{recommended}'" if recommended else f"{verb} '{name}'"

    return {
        "code": match.group("code"),
        "level": match.group("level"),
        "name": name,
        "verb": verb,
        "recommended": recommended,
        "assessment": ", ".join(assessment_tags),
        "tags": assessment_tags,
        "full_text": cleaned,
        "description": description
    }

def _parse_section_title(text: str) -> Optional[str]:
    cleaned = _strip_page_suffix(text)
    match = SECTION_RE.match(cleaned)
    if not match or "." not in match.group(1) or ITEM_START_RE.match(cleaned):
        return None
    return match.group(2).strip()

def _item_quality(item: Dict[str, Any]) -> Any:
    return (
        1 if item.get("assessment") else 0,
        1 if item.get("recommended") else 0,
        -len(item.get("full_text", ""))
    )

def _has_trailing_tags(text: str) -> bool:
    return bool(TRAILING_TAGS_RE.search(_strip_page_suffix(text)))

def parse_benchmark_txt(txt_path: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    current_section_title: Optional[str] = None
    pending_item_lines: List[str] = []

    def flush_item() -> None:
        nonlocal pending_item_lines
        if not pending_item_lines:
            return
        item = _parse_item_record(" ".join(pending_item_lines))
        pending_item_lines = []
        if not item:
            return
        item["category"] = current_section_title or ""
        items.append(item)

    with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
        for raw in f:
            line = _normalize_text(raw)
            if not line or PAGE_RE.match(line):
                continue
            if ITEM_START_RE.match(line):
                flush_item()
                pending_item_lines = [line]
                continue
            if pending_item_lines:
                section_title = _parse_section_title(line)
                if section_title is not None:
                    flush_item()
                    current_section_title = section_title
                    continue
                if _has_trailing_tags(" ".join(pending_item_lines)):
                    flush_item()
                    section_title = _parse_section_title(line)
                    if section_title is not None:
                        current_section_title = section_title
                    continue
                pending_item_lines.append(line)
                continue
            section_title = _parse_section_title(line)
            if section_title is not None:
                current_section_title = section_title

    flush_item()
    unique_items: Dict[str, Dict[str, Any]] = {}
    ordered_codes: List[str] = []
    for item in items:
        code = item["code"]
        existing = unique_items.get(code)
        if existing is None:
            unique_items[code] = item
            ordered_codes.append(code)
            continue
        if _item_quality(item) > _item_quality(existing):
            unique_items[code] = item
    return [unique_items[code] for code in ordered_codes]

def build_benchmark_metadata_index(txt_path: str) -> Dict[str, Dict[str, Any]]:
    return {item["code"]: item for item in parse_benchmark_txt(txt_path)}

def write_items_json(items: List[Dict[str, Any]], out_path: str) -> None:
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

def main():
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    txt_path = os.path.join(base_dir, "CIS_Microsoft_Windows_Server_2022_Benchmark_v4.0.0.txt")
    out_path = os.path.join(base_dir, "data", "cis_items.json")
    items = parse_benchmark_txt(txt_path)
    write_items_json(items, out_path)

if __name__ == "__main__":
    main()
