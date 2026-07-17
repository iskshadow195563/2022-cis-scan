import json
import os
import tempfile
from typing import Optional


PROFILES_DIR_NAME = "profiles"


def _get_profiles_dir() -> str:
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    profiles_dir = os.path.join(base_dir, PROFILES_DIR_NAME)
    os.makedirs(profiles_dir, exist_ok=True)
    return profiles_dir


def _profile_path(name: str) -> str:
    profiles_dir = _get_profiles_dir()
    safe_name = name.strip().replace("/", "_").replace("\\", "_").replace(":", "_")
    return os.path.join(profiles_dir, f"{safe_name}.json")


def list_profiles() -> list[dict]:
    profiles_dir = _get_profiles_dir()
    profiles = []
    for filename in sorted(os.listdir(profiles_dir)):
        if filename.endswith(".json"):
            filepath = os.path.join(profiles_dir, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                profiles.append({
                    "name": data.get("name", filename[:-5]),
                    "target_os": data.get("target_os", ""),
                    "description": data.get("description", ""),
                    "items": data.get("items", []),
                    "filename": filename,
                })
            except Exception:
                continue
    return profiles


def get_profile(name: str) -> Optional[dict]:
    filepath = _profile_path(name)
    if not os.path.exists(filepath):
        return None
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def save_profile(name: str, target_os: str, description: str, items: list[str]) -> tuple[bool, str]:
    if not name or not name.strip():
        return False, "Profile name is required."
    safe_name = name.strip()
    data = {
        "name": safe_name,
        "target_os": target_os.strip(),
        "description": description.strip(),
        "items": items,
    }
    filepath = _profile_path(safe_name)
    try:
        fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="profile_", dir=_get_profiles_dir())
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, filepath)
        finally:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass
        return True, safe_name
    except Exception as e:
        return False, str(e)


def delete_profile(name: str) -> tuple[bool, str]:
    filepath = _profile_path(name)
    if not os.path.exists(filepath):
        return False, "Profile not found."
    try:
        os.remove(filepath)
        return True, ""
    except Exception as e:
        return False, str(e)


def export_profile_to_file(name: str, export_path: str) -> tuple[bool, str]:
    profile = get_profile(name)
    if profile is None:
        return False, "Profile not found."
    try:
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, ensure_ascii=False, indent=2)
        return True, export_path
    except Exception as e:
        return False, str(e)


def import_profile_from_file(import_path: str) -> tuple[bool, str]:
    if not os.path.exists(import_path):
        return False, "File not found."
    try:
        with open(import_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        return False, f"Invalid JSON file: {e}"

    name = data.get("name", "").strip()
    if not name:
        return False, "Profile name is missing in the file."
    target_os = data.get("target_os", "").strip()
    description = data.get("description", "").strip()
    items = data.get("items", [])
    if not isinstance(items, list):
        items = []

    return save_profile(name, target_os, description, items)
