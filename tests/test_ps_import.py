import os
import tempfile
import unittest

from core.ps_import import (
    build_description,
    is_valid_script_number,
    normalize_powershell_script_text,
    normalize_ps_code,
    sanitize_filename_component,
    save_powershell_script,
)


class TestPsImport(unittest.TestCase):
    def test_number_validation(self):
        self.assertTrue(is_valid_script_number("1"))
        self.assertTrue(is_valid_script_number("9.1.1"))
        self.assertTrue(is_valid_script_number("  9.1.1  "))
        self.assertFalse(is_valid_script_number(""))
        self.assertFalse(is_valid_script_number("PS:9.1.1"))
        self.assertFalse(is_valid_script_number("9.1.a"))

    def test_code_normalization(self):
        self.assertEqual(normalize_ps_code("9.1.1"), "PS:9.1.1")
        self.assertEqual(normalize_ps_code(" PS:9.1.1 "), "PS:9.1.1")
        self.assertEqual(normalize_ps_code(""), "")

    def test_description_build(self):
        self.assertEqual(build_description("Firewall Status", "auto"), "Firewall Status (Automated)")
        self.assertEqual(build_description("Firewall Status", "ms only"), "Firewall Status (MS only, Automated)")
        self.assertEqual(build_description("Firewall Status", "manual"), "Firewall Status (Manual)")

    def test_script_normalization_strips_markdown_fences(self):
        raw = "```powershell\nWrite-Host 'Hi'\n```"
        normalized = normalize_powershell_script_text(raw)
        self.assertIn("Write-Host", normalized)
        self.assertNotIn("```", normalized)
        self.assertTrue(normalized.endswith("\r\n"))

    def test_filename_sanitization(self):
        self.assertEqual(sanitize_filename_component("a<b>c", "x"), "a_b_c")
        self.assertEqual(sanitize_filename_component("CON", "x"), "_CON")
        self.assertEqual(sanitize_filename_component("   ", "x"), "x")

    def test_save_script_writes_file(self):
        with tempfile.TemporaryDirectory() as td:
            p1 = save_powershell_script("Write-Output 1", td, "test")
            self.assertTrue(os.path.isfile(p1))
            p2 = save_powershell_script("Write-Output 2", td, "test")
            self.assertTrue(os.path.isfile(p2))
            self.assertNotEqual(p1, p2)


if __name__ == "__main__":
    unittest.main()
