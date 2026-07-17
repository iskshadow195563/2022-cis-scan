import os
import tempfile
import unittest

from core.config_manager import ConfigManager


class TestConfigManager(unittest.TestCase):
    def test_load_defaults_and_save(self):
        with tempfile.TemporaryDirectory() as td:
            cfg_path = os.path.join(td, "config.json")
            cm = ConfigManager(cfg_path)
            data = cm.get()
            self.assertIn("boot_animation", data)
            self.assertIn("startup", data)
            self.assertFalse(data["startup"]["first_launch_completed"])
            self.assertTrue(cm.save())
            self.assertTrue(os.path.exists(cfg_path))

    def test_update_and_clamp_duration(self):
        with tempfile.TemporaryDirectory() as td:
            cm = ConfigManager(os.path.join(td, "config.json"))
            cm.update("boot_animation.duration_sec", 20)
            self.assertEqual(cm.get()["boot_animation"]["duration_sec"], 10)
            cm.update("boot_animation.duration_sec", 1)
            self.assertEqual(cm.get()["boot_animation"]["duration_sec"], 3)


if __name__ == "__main__":
    unittest.main()
