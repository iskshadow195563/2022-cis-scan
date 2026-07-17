import json
import os
import subprocess
import unittest


class TestCisCheckFramework(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        cls.script_path = os.path.join(base_dir, "scripts", "cis_check_framework.ps1")

    def test_mapping_json_parameter_supports_remote_scans(self):
        mapping_json = json.dumps({
            "1.1.1": {
                "action": "not_applicable",
                "reboot": False,
            }
        })
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                self.script_path,
                "-Code",
                "1.1.1",
                "-MappingJson",
                mapping_json,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        lines = [line for line in completed.stdout.splitlines() if line.strip()]
        data = json.loads(lines[-1])
        self.assertEqual(data["Status"], "UNSUPPORTED")
        self.assertEqual(data["Detail"], "dc_only_or_ms_only_or_manual")


if __name__ == "__main__":
    unittest.main()
