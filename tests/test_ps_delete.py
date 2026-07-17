import os
import tempfile
import unittest

from core.ps_import import delete_script_file


class TestPsDelete(unittest.TestCase):
    def test_delete_missing_file_is_ok(self):
        ok, _detail = delete_script_file(os.path.join(tempfile.gettempdir(), "file_that_should_not_exist_12345.ps1"))
        self.assertTrue(ok)

    def test_delete_empty_path_fails(self):
        ok, _detail = delete_script_file("")
        self.assertFalse(ok)

    def test_delete_existing_file(self):
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "a.ps1")
            with open(p, "w", encoding="utf-8") as f:
                f.write("Write-Output 1")
            ok, _detail = delete_script_file(p)
            self.assertTrue(ok)
            self.assertFalse(os.path.exists(p))


if __name__ == "__main__":
    unittest.main()
