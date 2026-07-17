import ctypes
import os
import subprocess
import sys

from PyQt5.QtCore import QSettings

try:
    import winreg
except Exception:
    winreg = None


SPI_SETCURSORS = 0x0057
SPIF_SENDCHANGE = 0x0002


def _coerce_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _default_base_dir():
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return meipass
        return os.path.dirname(sys.executable)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class CursorManager:
    def __init__(self, settings=None, base_dir=None, platform_name=None):
        self.settings = settings or QSettings("HKIIT", "WindowsSecurityAuditor")
        self.base_dir = base_dir or _default_base_dir()
        self.platform_name = platform_name or sys.platform
        self.mouse_dir = os.path.join(self.base_dir, "mouse")
        self.install_inf = os.path.join(self.mouse_dir, "install.inf")
        self.setting_key = "ui/custom_cursor_enabled"
        self.cursor_value_map = {
            "AppStarting": "working",
            "Arrow": "pointer",
            "crosshair": "precision",
            "precisionhair": "precision",
            "Hand": "link",
            "Help": "help",
            "IBeam": "text",
            "No": "unavailable",
            "NWPen": "hand",
            "SizeAll": "move",
            "SizeNESW": "dgn2",
            "SizeNS": "vert",
            "SizeNWSE": "dgn1",
            "SizeWE": "horz",
            "UpArrow": "alternate",
            "Wait": "busy",
            "Pin": "pin",
            "Person": "person",
        }
        self.scheme_order = [
            "pointer",
            "help",
            "working",
            "busy",
            "precision",
            "text",
            "hand",
            "unavailable",
            "vert",
            "horz",
            "dgn1",
            "dgn2",
            "move",
            "alternate",
            "link",
            "pin",
            "person",
        ]

    def is_windows(self):
        return self.platform_name.startswith("win")

    def preferred_enabled(self):
        return _coerce_bool(self.settings.value(self.setting_key, False))

    def set_preferred_enabled(self, enabled):
        self.settings.setValue(self.setting_key, bool(enabled))

    def apply_startup_preference(self):
        if not self.is_windows():
            self.set_preferred_enabled(False)
            return False, "Not running on Windows."
        ok, message = self.ensure_installed()
        if not ok and self.preferred_enabled():
            self.set_preferred_enabled(False)
            self.disable_custom_scheme(save_preference=False)
            return False, message
        if self.preferred_enabled():
            apply_ok, apply_message = self._apply_custom_scheme()
            if not apply_ok:
                self.set_preferred_enabled(False)
                self.disable_custom_scheme(save_preference=False)
                return False, apply_message
            return True, ""
        self.disable_custom_scheme(save_preference=False)
        return False, message if not ok else ""

    def enable_custom_scheme(self):
        if not self.is_windows():
            self.set_preferred_enabled(False)
            return False, "Custom cursor is only supported on Windows."
        ok, message = self.ensure_installed()
        if not ok:
            self.set_preferred_enabled(False)
            self.disable_custom_scheme(save_preference=False)
            return False, message
        ok, message = self._apply_custom_scheme()
        if ok:
            self.set_preferred_enabled(True)
            return True, ""
        self.set_preferred_enabled(False)
        self.disable_custom_scheme(save_preference=False)
        return False, message

    def disable_custom_scheme(self, save_preference=True):
        if save_preference:
            self.set_preferred_enabled(False)
        if not self.is_windows() or winreg is None:
            return True, ""
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors", 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_EXPAND_SZ, "")
                for cursor_name in self.cursor_value_map:
                    winreg.SetValueEx(key, cursor_name, 0, winreg.REG_EXPAND_SZ, "")
            self._refresh_system_cursors()
            if not self._verify_reset_to_default():
                return False, "Registry verification failed while disabling cursor scheme."
            return True, ""
        except Exception as exc:
            return False, str(exc)

    def ensure_installed(self):
        if not self.is_windows():
            return False, "Not running on Windows."
        if winreg is None:
            return False, "winreg is not available."
        if not os.path.exists(self.install_inf):
            return False, f"install.inf not found: {self.install_inf}"
        scheme_name, _cursor_dir, cursor_names = self._parse_install_inf()
        if self._scheme_exists(scheme_name):
            return True, ""
        run_ok, run_err = self._run_silent_install()
        if run_ok and self._scheme_exists(scheme_name):
            return True, ""
        fallback_ok, fallback_err = self._register_scheme_from_files(scheme_name, cursor_names)
        if fallback_ok and self._scheme_exists(scheme_name):
            return True, ""
        err_parts = []
        if run_err:
            err_parts.append(run_err)
        if fallback_err:
            err_parts.append(fallback_err)
        if not err_parts:
            err_parts.append("Cursor scheme registration failed.")
        return False, " | ".join(err_parts)

    def _run_silent_install(self):
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        cmd = [
            "rundll32.exe",
            "setupapi,InstallHinfSection",
            "DefaultInstall",
            "132",
            self.install_inf,
        ]
        try:
            completed = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                creationflags=creationflags,
                check=False,
            )
        except Exception as exc:
            return False, str(exc)
        if completed.returncode == 0:
            return True, ""
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        detail = stderr or stdout or f"exit code {completed.returncode}"
        return False, f"install.inf execution failed: {detail}"

    def _apply_custom_scheme(self):
        if winreg is None:
            return False, "winreg is not available."
        scheme_name, _cursor_dir, _cursor_names = self._parse_install_inf()
        if not self._scheme_exists(scheme_name):
            return False, "Cursor scheme registry entry is missing."
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors", 0, winreg.KEY_SET_VALUE) as key:
                winreg.SetValueEx(key, "", 0, winreg.REG_EXPAND_SZ, scheme_name)
            self._refresh_system_cursors()
            if not self._verify_scheme_binding(scheme_name):
                return False, "Registry verification failed while enabling cursor scheme."
            return True, ""
        except Exception as exc:
            return False, str(exc)

    def _scheme_exists(self, scheme_name):
        if winreg is None:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors\Schemes", 0, winreg.KEY_READ) as key:
                value, _ = winreg.QueryValueEx(key, scheme_name)
            return bool(str(value).strip())
        except Exception:
            return False

    def _register_scheme_from_files(self, scheme_name, cursor_names):
        if winreg is None:
            return False, "winreg is not available."
        try:
            scheme_paths = []
            resolved = {}
            for token in self.scheme_order:
                name = cursor_names.get(token)
                if not name:
                    return False, f"Missing cursor token in install.inf: {token}"
                full_path = os.path.join(self.mouse_dir, name)
                if not os.path.exists(full_path):
                    return False, f"Cursor file not found: {full_path}"
                full_path = os.path.abspath(full_path)
                resolved[token] = full_path
                scheme_paths.append(full_path)

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors\Schemes", 0, winreg.KEY_SET_VALUE) as schemes:
                winreg.SetValueEx(schemes, scheme_name, 0, winreg.REG_EXPAND_SZ, ",".join(scheme_paths))

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors", 0, winreg.KEY_SET_VALUE) as cursors:
                winreg.SetValueEx(cursors, "", 0, winreg.REG_EXPAND_SZ, scheme_name)
                for reg_name, token in self.cursor_value_map.items():
                    winreg.SetValueEx(cursors, reg_name, 0, winreg.REG_EXPAND_SZ, resolved[token])
            return True, ""
        except Exception as exc:
            return False, str(exc)

    def _refresh_system_cursors(self):
        user32 = ctypes.windll.user32
        user32.SystemParametersInfoW(SPI_SETCURSORS, 0, None, SPIF_SENDCHANGE)
        creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.run(
            ["rundll32.exe", "user32.dll,UpdatePerUserSystemParameters"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=creationflags,
            check=False,
        )

    def _verify_scheme_binding(self, scheme_name):
        if winreg is None:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors", 0, winreg.KEY_READ) as key:
                current, _ = winreg.QueryValueEx(key, "")
                current = str(current or "").strip()
                if current != scheme_name:
                    return False
                for cursor_name in self.cursor_value_map:
                    value, _ = winreg.QueryValueEx(key, cursor_name)
                    if not str(value or "").strip():
                        return False
            return True
        except Exception:
            return False

    def _verify_reset_to_default(self):
        if winreg is None:
            return False
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Cursors", 0, winreg.KEY_READ) as key:
                current, _ = winreg.QueryValueEx(key, "")
                if str(current or "").strip():
                    return False
            return True
        except Exception:
            return False

    def _parse_install_inf(self):
        scheme_name = "Custom Cursor Scheme"
        cursor_dir = ""
        cursor_names = {}
        try:
            with open(self.install_inf, "r", encoding="utf-8", errors="ignore") as f:
                lines = [line.strip() for line in f.readlines()]
        except Exception:
            return scheme_name, cursor_dir, cursor_names

        in_strings = False
        for line in lines:
            if not line:
                continue
            if line.startswith("[") and line.endswith("]"):
                in_strings = line.lower() == "[strings]"
                continue
            if not in_strings:
                continue
            if "=" not in line:
                continue
            key, value = [part.strip() for part in line.split("=", 1)]
            value = value.strip().strip('"')
            if key == "SCHEME_NAME":
                scheme_name = value or scheme_name
            elif key == "CUR_DIR":
                cursor_dir = value
            else:
                cursor_names[key] = value
        return scheme_name, cursor_dir, cursor_names
