import json
import os
import tempfile
from typing import Any, Dict

DEFAULT_CONFIG: Dict[str, Any] = {
    "boot_animation": {
        "enabled": True,
        "duration_sec": 5,
    },
    "startup": {
        "first_launch_completed": False,
    },
}


class ConfigManager:
    def __init__(self, config_path: str = None):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        self.config_path = config_path or os.path.join(base_dir, "config.json")
        self._data: Dict[str, Any] = {}
        self.load()

    def load(self):
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            else:
                self._data = {}
        except Exception:
            self._data = {}
        self._apply_defaults()

    def save(self) -> bool:
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(suffix=".json", prefix="cfg_", dir=os.path.dirname(self.config_path))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(self._data, f, ensure_ascii=False, indent=2)
                os.replace(tmp_path, self.config_path)
            finally:
                try:
                    if os.path.exists(tmp_path):
                        os.remove(tmp_path)
                except Exception:
                    pass
            return True
        except Exception:
            return False

    def _apply_defaults(self):
        def deep_merge(dst: Dict[str, Any], src: Dict[str, Any]):
            for k, v in src.items():
                if isinstance(v, dict):
                    dst[k] = deep_merge(dst.get(k, {}) if isinstance(dst.get(k), dict) else {}, v)
                else:
                    dst.setdefault(k, v)
            return dst

        self._data = deep_merge(self._data or {}, DEFAULT_CONFIG)
        boot_animation = self._data.get("boot_animation")
        if not isinstance(boot_animation, dict):
            boot_animation = dict(DEFAULT_CONFIG["boot_animation"])
            self._data["boot_animation"] = boot_animation

        try:
            duration_sec = int(boot_animation.get("duration_sec", DEFAULT_CONFIG["boot_animation"]["duration_sec"]))
        except Exception:
            duration_sec = DEFAULT_CONFIG["boot_animation"]["duration_sec"]
        boot_animation["duration_sec"] = max(3, min(10, duration_sec))
        boot_animation["enabled"] = bool(boot_animation.get("enabled", DEFAULT_CONFIG["boot_animation"]["enabled"]))

    def get(self) -> Dict[str, Any]:
        return self._data

    def update(self, path: str, value: Any) -> bool:
        keys = path.split(".")
        cur = self._data
        for k in keys[:-1]:
            if k not in cur or not isinstance(cur[k], dict):
                cur[k] = {}
            cur = cur[k]
        cur[keys[-1]] = value
        self._apply_defaults()
        return self.save()
