import os
import tempfile
import unittest

from gui.background_manager import BackgroundManager, is_supported_image_file


class _FakeSettings:
    def __init__(self):
        self._store = {}

    def setValue(self, key, value):
        self._store[key] = value

    def value(self, key, default=None):
        return self._store.get(key, default)


class TestBackgroundManager(unittest.TestCase):
    def test_supported_extensions(self):
        self.assertTrue(is_supported_image_file("a.png"))
        self.assertTrue(is_supported_image_file("a.jpg"))
        self.assertTrue(is_supported_image_file("a.jpeg"))
        self.assertTrue(is_supported_image_file("a.webp"))
        self.assertTrue(is_supported_image_file("a.gif"))
        self.assertFalse(is_supported_image_file(""))

    def test_list_images_filters_non_images(self):
        with tempfile.TemporaryDirectory() as td:
            open(os.path.join(td, "a.png"), "wb").close()
            open(os.path.join(td, "b.txt"), "wb").close()
            mgr = BackgroundManager(background_dir=td, settings=_FakeSettings())
            items = mgr.list_images()
            self.assertEqual(len(items), 1)
            self.assertTrue(items[0].endswith("a.png"))

    def test_selected_path_persists(self):
        with tempfile.TemporaryDirectory() as td:
            settings = _FakeSettings()
            mgr = BackgroundManager(background_dir=td, settings=settings)
            mgr.set_selected_path(os.path.join(td, "x.png"))
            self.assertEqual(settings.value("ui/background_image"), os.path.join(td, "x.png"))


if __name__ == "__main__":
    unittest.main()
