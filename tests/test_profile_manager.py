import os
import tempfile
import unittest

from core.profile_manager import (
    save_profile, list_profiles, get_profile, delete_profile,
    export_profile_to_file, import_profile_from_file, _get_profiles_dir
)


class TestProfileManager(unittest.TestCase):
    def setUp(self):
        self.profiles_dir = _get_profiles_dir()
        self.test_name = "Unittest Profile"
        self.test_items = ["1.1.1", "1.1.2", "2.2.1"]
        self.cleanup_test_profiles()

    def tearDown(self):
        self.cleanup_test_profiles()

    def cleanup_test_profiles(self):
        for p in list_profiles():
            if p["name"].startswith("Unittest"):
                delete_profile(p["name"])

    def test_save_and_list(self):
        ok, name = save_profile(self.test_name, "Windows Server 2022", "Test", self.test_items)
        self.assertTrue(ok)
        self.assertEqual(name, self.test_name)
        profiles = list_profiles()
        names = [p["name"] for p in profiles]
        self.assertIn(self.test_name, names)

    def test_get_profile(self):
        save_profile(self.test_name, "Windows Server 2022", "Test desc", self.test_items)
        p = get_profile(self.test_name)
        self.assertIsNotNone(p)
        self.assertEqual(p["name"], self.test_name)
        self.assertEqual(p["target_os"], "Windows Server 2022")
        self.assertEqual(p["description"], "Test desc")
        self.assertEqual(p["items"], self.test_items)

    def test_delete_profile(self):
        save_profile(self.test_name, "", "", self.test_items)
        ok, err = delete_profile(self.test_name)
        self.assertTrue(ok, f"Delete failed: {err}")
        p = get_profile(self.test_name)
        self.assertIsNone(p)

    def test_export_and_import(self):
        save_profile(self.test_name, "Windows 11", "Export test", self.test_items)
        tmp_path = os.path.join(tempfile.gettempdir(), "unittest_export_profile.json")
        try:
            ok, path = export_profile_to_file(self.test_name, tmp_path)
            self.assertTrue(ok)
            self.assertTrue(os.path.exists(path))

            delete_profile(self.test_name)
            p = get_profile(self.test_name)
            self.assertIsNone(p)

            ok, imported_name = import_profile_from_file(tmp_path)
            self.assertTrue(ok)
            self.assertEqual(imported_name, self.test_name)

            p = get_profile(self.test_name)
            self.assertIsNotNone(p)
            self.assertEqual(p["target_os"], "Windows 11")
            self.assertEqual(p["items"], self.test_items)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_save_empty_name(self):
        ok, err = save_profile("", "", "", [])
        self.assertFalse(ok)

    def test_import_invalid_file(self):
        ok, err = import_profile_from_file("nonexistent_file.json")
        self.assertFalse(ok)

    def test_delete_nonexistent(self):
        ok, err = delete_profile("nonexistent_profile_name_12345")
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
