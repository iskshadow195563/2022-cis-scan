import os
import json
import tempfile
import unittest

from PyQt5.QtWidgets import QApplication

from gui.main_window import MainWindow
from core.language_manager import tr


class TestMainWindowApplyDefaultsButton(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._app = QApplication.instance() or QApplication([])

    def test_button_visible_in_main_ui(self):
        window = MainWindow()
        self.assertTrue(hasattr(window, "btn_apply_defaults"))
        btn = window.btn_apply_defaults
        self.assertEqual(btn.objectName(), "applyDefaultsButton")
        self.assertEqual(btn.text(), tr("apply_defaults"))
        self.assertTrue(bool(btn.toolTip()))

    def test_build_apply_defaults_process_args(self):
        window = MainWindow()
        report_dir = os.path.join(os.getcwd(), "results", "cis_apply_test")

        program, args = window.build_apply_defaults_process_args(["1.1.1", "1.1.2"], report_dir, undo=False)
        self.assertEqual(program.lower(), "powershell.exe")
        self.assertIn("-Items", args)
        self.assertIn("1.1.1", args)
        self.assertIn("1.1.2", args)
        self.assertIn("-ReportDir", args)

        program, args = window.build_apply_defaults_process_args([], report_dir, undo=False)
        self.assertIn("-SelectAll", args)

        program, args = window.build_apply_defaults_process_args([], report_dir, undo=True)
        self.assertIn("-Undo", args)

    def test_save_and_restore_baseline_args(self):
        window = MainWindow()
        # Save baseline
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        script_path = os.path.join(base_dir, "scripts", "cis_apply.ps1")
        self.assertTrue(os.path.exists(script_path))
        # start_save_baseline/start_restore_baseline use QProcess directly; verify localized texts exist
        self.assertTrue(tr("apply_defaults_save_baseline"))
        self.assertTrue(tr("apply_defaults_restore_baseline"))

    def test_custom_mapping_preferred(self):
        window = MainWindow()
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        custom_mapping = os.path.join(base_dir, "data", "cis_mapping.custom.json")
        try:
            # create a temporary custom mapping file
            os.makedirs(os.path.dirname(custom_mapping), exist_ok=True)
            with open(custom_mapping, "w", encoding="utf-8") as f:
                f.write("{}")
            program, args = window.build_apply_defaults_process_args([], os.path.join(os.getcwd(), "results"), undo=False)
            # ensure mapping path points to custom mapping
            idx = args.index("-MappingPath") + 1
            self.assertEqual(args[idx], custom_mapping)
        finally:
            if os.path.exists(custom_mapping):
                os.remove(custom_mapping)

    def test_relative_builtin_script_is_not_reported_missing(self):
        window = MainWindow()
        missing = window._get_items_without_scripts([
            {"code": "1.1.1", "script_path": "scripts\\checks\\check_1_1_1.ps1"}
        ])
        self.assertEqual(missing, [])

    def test_latest_report_ignores_non_scan_json(self):
        window = MainWindow()
        with tempfile.TemporaryDirectory() as td:
            report_path = os.path.join(td, "report_20260101_000000.json")
            noise_path = os.path.join(td, "hallucination_20260102_000000.json")
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump({"scan_info": {}, "results": []}, f)
            with open(noise_path, "w", encoding="utf-8") as f:
                json.dump({"total_issues": 1}, f)

            os.utime(report_path, (100, 100))
            os.utime(noise_path, (200, 200))

            self.assertEqual(window.find_latest_report(td), report_path)

    def test_apply_profile_codes_selects_main_table_items(self):
        window = MainWindow()
        window.apply_profile_codes(["1.1.1", "1.1.2"])
        self.assertIn("1.1.1", window.selected_codes)
        self.assertIn("1.1.2", window.selected_codes)
        checked = set(window.collect_checked_cis_codes())
        self.assertIn("1.1.1", checked)
        self.assertIn("1.1.2", checked)

    def test_validate_remote_target_accepts_ip_and_domain_only(self):
        window = MainWindow()
        self.assertTrue(window.validate_remote_target("192.168.1.10"))
        self.assertTrue(window.validate_remote_target("server01.example.local"))
        self.assertFalse(window.validate_remote_target(""))
        self.assertFalse(window.validate_remote_target("http://server01"))
        self.assertFalse(window.validate_remote_target("server name"))
