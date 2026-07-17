import os
import tempfile
import unittest

import core.cursor_manager as cursor_module
from core.cursor_manager import CursorManager


class _FakeSettings:
    def __init__(self):
        self._store = {}

    def setValue(self, key, value):
        self._store[key] = value

    def value(self, key, default=None):
        return self._store.get(key, default)


class _KeyCtx:
    def __init__(self, reg, root, path):
        self._reg = reg
        self._root = root
        self._path = path

    def __enter__(self):
        self._reg._ensure_key(self._root, self._path)
        return (self._root, self._path)

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeWinReg:
    HKEY_CURRENT_USER = "HKCU"
    KEY_READ = 1
    KEY_SET_VALUE = 2
    REG_EXPAND_SZ = 1

    def __init__(self):
        self._data = {}

    def _ensure_key(self, root, path):
        self._data.setdefault((root, path), {})

    def OpenKey(self, root, path, _reserved=0, _access=0):
        return _KeyCtx(self, root, path)

    def SetValueEx(self, key, name, _reserved, _reg_type, value):
        self._ensure_key(*key)
        self._data[key][name] = value

    def QueryValueEx(self, key, name):
        self._ensure_key(*key)
        if name not in self._data[key]:
            raise FileNotFoundError(name)
        return self._data[key][name], self.REG_EXPAND_SZ


def _write_install_inf(path):
    content = """
[Strings]
CUR_DIR = "mouse"
SCHEME_NAME = "Test Cursor"
pointer = "Normal.ani"
help = "Help.ani"
working = "Working.ani"
busy = "Busy.ani"
precision = "Precision.ani"
text = "Text.ani"
hand = "Handwriting.ani"
unavailable = "Unavailable.ani"
vert = "Vertical.ani"
horz = "Horizontal.ani"
dgn1 = "Diagonal1.ani"
dgn2 = "Diagonal2.ani"
move = "Move.ani"
alternate = "Alternate.ani"
link = "Link.ani"
pin = "Pin.ani"
person = "Person.ani"
""".strip()
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _touch_cursor_files(mouse_dir):
    names = [
        "Normal.ani",
        "Help.ani",
        "Working.ani",
        "Busy.ani",
        "Precision.ani",
        "Text.ani",
        "Handwriting.ani",
        "Unavailable.ani",
        "Vertical.ani",
        "Horizontal.ani",
        "Diagonal1.ani",
        "Diagonal2.ani",
        "Move.ani",
        "Alternate.ani",
        "Link.ani",
        "Pin.ani",
        "Person.ani",
    ]
    for name in names:
        with open(os.path.join(mouse_dir, name), "wb") as f:
            f.write(b"0")


class TestCursorManager(unittest.TestCase):
    def setUp(self):
        self._old_winreg = cursor_module.winreg
        cursor_module.winreg = _FakeWinReg()

    def tearDown(self):
        cursor_module.winreg = self._old_winreg

    def test_missing_install_inf_returns_error(self):
        with tempfile.TemporaryDirectory() as td:
            manager = CursorManager(settings=_FakeSettings(), base_dir=td, platform_name="win32")
            ok, message = manager.ensure_installed()
            self.assertFalse(ok)
            self.assertIn("install.inf not found", message)

    def test_fallback_registers_scheme_when_silent_install_fails(self):
        with tempfile.TemporaryDirectory() as td:
            mouse_dir = os.path.join(td, "mouse")
            os.makedirs(mouse_dir, exist_ok=True)
            _write_install_inf(os.path.join(mouse_dir, "install.inf"))
            _touch_cursor_files(mouse_dir)
            manager = CursorManager(settings=_FakeSettings(), base_dir=td, platform_name="win32")
            manager._run_silent_install = lambda: (False, "denied")
            ok, message = manager.ensure_installed()
            self.assertTrue(ok)
            self.assertEqual(message, "")
            self.assertTrue(manager._scheme_exists("Test Cursor"))

    def test_enable_and_disable_updates_preference(self):
        with tempfile.TemporaryDirectory() as td:
            mouse_dir = os.path.join(td, "mouse")
            os.makedirs(mouse_dir, exist_ok=True)
            _write_install_inf(os.path.join(mouse_dir, "install.inf"))
            _touch_cursor_files(mouse_dir)
            settings = _FakeSettings()
            manager = CursorManager(settings=settings, base_dir=td, platform_name="win32")
            manager._run_silent_install = lambda: (False, "denied")
            manager._refresh_system_cursors = lambda: None

            ok, message = manager.enable_custom_scheme()
            self.assertTrue(ok)
            self.assertEqual(message, "")
            self.assertTrue(manager.preferred_enabled())

            ok, message = manager.disable_custom_scheme()
            self.assertTrue(ok)
            self.assertEqual(message, "")
            self.assertFalse(manager.preferred_enabled())

    def test_startup_applies_when_preference_enabled(self):
        with tempfile.TemporaryDirectory() as td:
            mouse_dir = os.path.join(td, "mouse")
            os.makedirs(mouse_dir, exist_ok=True)
            _write_install_inf(os.path.join(mouse_dir, "install.inf"))
            _touch_cursor_files(mouse_dir)
            settings = _FakeSettings()
            settings.setValue("ui/custom_cursor_enabled", True)
            manager = CursorManager(settings=settings, base_dir=td, platform_name="win32")
            manager._run_silent_install = lambda: (False, "denied")
            manager._refresh_system_cursors = lambda: None

            enabled, message = manager.apply_startup_preference()
            self.assertTrue(enabled)
            self.assertEqual(message, "")
            self.assertTrue(manager.preferred_enabled())


if __name__ == "__main__":
    unittest.main()
