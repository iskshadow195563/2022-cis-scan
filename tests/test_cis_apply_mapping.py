import json
import os
import subprocess
import tempfile
import unittest


class TestCisApplyMapping(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.script_path = os.path.join(base_dir, "scripts", "cis_apply.ps1")

    def run_ps(self, command: str) -> str:
        full_command = f". '{self.script_path}'; {command}"
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                full_command,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        return lines[-1] if lines else ""

    def write_json(self, path: str, data) -> None:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False, indent=2)

    def test_save_custom_mapping_preserves_code_keys(self):
        with tempfile.TemporaryDirectory() as td:
            base_path = os.path.join(td, "cis_mapping.json")
            custom_path = os.path.join(td, "cis_mapping.custom.json")
            self.write_json(
                base_path,
                {
                    "1.1.1": {
                        "action": "secedit_system_access",
                        "system_access": {"PasswordHistorySize": 24},
                        "reboot": False,
                    },
                    "1.1.2": {
                        "action": "net_accounts",
                        "args": ["/MAXPWAGE:365"],
                        "reboot": False,
                    },
                    "2.3.2.1": {
                        "action": "auditpol",
                        "subcategory": "Audit Policy Change",
                        "success": "enable",
                        "failure": "enable",
                        "reboot": False,
                    },
                },
            )

            command = (
                f"$base = ConvertTo-MappingHashtable -Object (Load-Json -path '{base_path}'); "
                f"$result = Save-CustomMapping -BaseMap $base -sa @{{ PasswordHistorySize = '12' }} "
                f"-netArgs @('/MAXPWAGE:42') -path '{custom_path}'; "
                "$result | ConvertTo-Json -Depth 10 -Compress"
            )
            data = json.loads(self.run_ps(command))

            self.assertEqual(sorted(data.keys()), ["1.1.1", "1.1.2", "2.3.2.1"])
            self.assertEqual(str(data["1.1.1"]["system_access"]["PasswordHistorySize"]), "12")
            self.assertEqual(data["1.1.2"]["args"], ["/MAXPWAGE:42"])
            self.assertEqual(data["2.3.2.1"]["action"], "auditpol")

    def test_load_mapping_merges_base_and_custom_and_ignores_legacy_keys(self):
        with tempfile.TemporaryDirectory() as td:
            base_path = os.path.join(td, "cis_mapping.json")
            custom_path = os.path.join(td, "cis_mapping.custom.json")
            self.write_json(
                base_path,
                {
                    "1.1.1": {
                        "action": "secedit_system_access",
                        "system_access": {"PasswordHistorySize": 24},
                        "reboot": False,
                    },
                    "1.1.2": {
                        "action": "net_accounts",
                        "args": ["/MAXPWAGE:365"],
                        "reboot": False,
                    },
                },
            )
            self.write_json(
                custom_path,
                {
                    "Baseline:SystemAccess": {
                        "action": "secedit_system_access",
                        "system_access": {"PasswordHistorySize": 12},
                        "reboot": False,
                    },
                    "1.1.2": {
                        "action": "net_accounts",
                        "args": ["/MAXPWAGE:42"],
                        "reboot": False,
                    },
                },
            )

            command = f"(Load-MappingTable -MappingPath '{base_path}') | ConvertTo-Json -Depth 10 -Compress"
            data = json.loads(self.run_ps(command))

            self.assertEqual(sorted(data.keys()), ["1.1.1", "1.1.2"])
            self.assertEqual(data["1.1.2"]["args"], ["/MAXPWAGE:42"])

    def test_select_all_path_is_limited_to_mapped_items(self):
        with open(self.script_path, "r", encoding="utf-8") as fh:
            content = fh.read()

        self.assertIn("SelectAll requested; limiting selection to mapped items", content)
        self.assertIn("Get-ObjectValue -Object $map -Name $code", content)

    def test_net_accounts_compare_builds_real_apply_arguments(self):
        command = (
            "(@("
            "(Get-NetAccountsCompareArg -Key 'MinPasswordLength' -Expected 14),"
            "(Get-NetAccountsCompareArg -Key 'LockoutThreshold' -Expected 5),"
            "(Get-NetAccountsCompareArg -Key 'LockoutWindow' -Expected 15)"
            ") -join '|')"
        )
        self.assertEqual(
            self.run_ps(command),
            "/MINPWLEN:14|/LOCKOUTTHRESHOLD:5|/LOCKOUTWINDOW:15",
        )

    def test_save_custom_mapping_updates_net_accounts_compare_expected_value(self):
        with tempfile.TemporaryDirectory() as td:
            base_path = os.path.join(td, "cis_mapping.json")
            custom_path = os.path.join(td, "cis_mapping.custom.json")
            self.write_json(
                base_path,
                {
                    "1.1.4": {
                        "action": "net_accounts_compare",
                        "key": "MinPasswordLength",
                        "compare_op": "ge",
                        "expected": 14,
                        "reboot": False,
                    },
                },
            )

            command = (
                f"$base = ConvertTo-MappingHashtable -Object (Load-Json -path '{base_path}'); "
                f"$result = Save-CustomMapping -BaseMap $base -sa @{{}} "
                f"-netArgs @('/MINPWLEN:12') -path '{custom_path}'; "
                "$result | ConvertTo-Json -Depth 10 -Compress"
            )
            data = json.loads(self.run_ps(command))

            self.assertEqual(str(data["1.1.4"]["expected"]), "12")

    def test_apply_script_contains_handlers_for_server_2022_mapping_actions(self):
        with open(self.script_path, "r", encoding="utf-8") as fh:
            content = fh.read()

        for action in [
            'action=net_accounts_compare',
            'action=gpo_setting',
            'action=firewall_profile',
            'action=service',
            'action=secedit_privilege_rights',
        ]:
            self.assertIn(action, content)


if __name__ == "__main__":
    unittest.main()
