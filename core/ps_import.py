import os
import re


MODE_AUTO = "auto"
MODE_MS_ONLY = "ms only"
MODE_MANUAL = "manual"

VALID_MODES = {MODE_AUTO, MODE_MS_ONLY, MODE_MANUAL}


_NUMBER_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)*$")


def normalize_script_number(number_text: str) -> str:
    return (number_text or "").strip()


def is_valid_script_number(number_text: str) -> bool:
    number = normalize_script_number(number_text)
    if not number:
        return False
    return bool(_NUMBER_RE.match(number))


def normalize_ps_code(number_text: str) -> str:
    number = normalize_script_number(number_text)
    if not number:
        return ""
    if number.upper().startswith("PS:"):
        number = number[3:].strip()
    return f"PS:{number}"


def normalize_mode(mode_text: str) -> str:
    return (mode_text or "").strip().lower()


def assessment_text_for_mode(mode_text: str) -> str:
    mode = normalize_mode(mode_text)
    if mode == MODE_AUTO:
        return "Automated"
    if mode == MODE_MS_ONLY:
        return "MS only, Automated"
    if mode == MODE_MANUAL:
        return "Manual"
    return ""


def build_description(script_name: str, mode_text: str) -> str:
    name = (script_name or "").strip()
    assessment = assessment_text_for_mode(mode_text)
    if not name:
        return ""
    if assessment:
        return f"{name} ({assessment})"
    return name


_INVALID_FILENAME_CHARS_RE = re.compile(r'[<>:"/\\|?*\x00-\x1F]')


def sanitize_filename_component(text: str, fallback: str) -> str:
    value = (text or "").strip()
    value = _INVALID_FILENAME_CHARS_RE.sub("_", value)
    value = value.strip(" .")
    if not value:
        value = fallback
    reserved = {
        "CON",
        "PRN",
        "AUX",
        "NUL",
        *(f"COM{i}" for i in range(1, 10)),
        *(f"LPT{i}" for i in range(1, 10)),
    }
    if value.upper() in reserved:
        value = f"_{value}"
    return value


def normalize_powershell_script_text(text: str) -> str:
    raw = text or ""
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = raw.split("\n")
    if len(lines) >= 2 and lines[0].strip().startswith("```") and lines[-1].strip() == "```":
        lines = lines[1:-1]
    return "\r\n".join(lines).strip() + "\r\n"


def ensure_unique_path(path: str) -> str:
    if not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    for idx in range(2, 10_000):
        candidate = f"{base}_{idx}{ext}"
        if not os.path.exists(candidate):
            return candidate
    raise RuntimeError("Unable to generate a unique filename.")


def save_powershell_script(script_text: str, target_dir: str, filename_base: str) -> str:
    os.makedirs(target_dir, exist_ok=True)
    safe_base = sanitize_filename_component(filename_base, "script")
    path = ensure_unique_path(os.path.join(target_dir, f"{safe_base}.ps1"))
    normalized = normalize_powershell_script_text(script_text)
    with open(path, "w", encoding="utf-8") as f:
        f.write(normalized)
    return path


def delete_script_file(path: str):
    p = (path or "").strip()
    if not p:
        return False, "Empty path."
    if not os.path.exists(p):
        return True, "File not found."
    try:
        os.remove(p)
        return True, "Deleted."
    except PermissionError:
        return False, "Permission denied."
    except OSError as e:
        return False, str(e)
