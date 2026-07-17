import os
import tempfile
import json
import unittest
from core.cis_parser import parse_benchmark_txt, write_items_json

class TestCisParser(unittest.TestCase):
    def test_parse_basic_items(self):
        content = """
1 Account Policies ................................................................................................................36
1.1 Password Policy ............................................................................................................................ 36
1.1.1 (L1) Ensure 'Enforce password history' is set to '24 or more password(s)' (Automated)
1.1.4 (L1) Ensure 'Minimum password length' is set to '14 or more character(s)' (Automated)
2 Local Policies .....................................................................................................................63
2.3.2.1 (L1) Ensure 'Audit: Force audit policy subcategory settings (Windows Vista or later) to override audit policy category settings' is set to 'Enabled' (Automated)
""".strip()
        with tempfile.TemporaryDirectory() as td:
            txt_path = os.path.join(td, "cis.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(content)
            items = parse_benchmark_txt(txt_path)
            self.assertTrue(any(i["code"] == "1.1.1" and i["recommended"] for i in items))
            self.assertTrue(any(i["code"] == "1.1.4" and i["recommended"] for i in items))
            self.assertTrue(any(i["code"] == "2.3.2.1" and i["recommended"] for i in items))
            out_path = os.path.join(td, "cis.json")
            write_items_json(items, out_path)
            with open(out_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.assertIsInstance(data, list)
            self.assertGreaterEqual(len(data), 3)

    def test_parse_assessment_tags_and_wrapped_lines(self):
        content = """
1.2.3 (L1) Ensure 'Allow Administrator account lockout' is set to 'Enabled' (MS only) (Manual)
 .................................................................................................................................................. 58
2.2.2 (L1) Ensure 'Access this computer from the network' is set to 'Administrators,
Authenticated Users, ENTERPRISE DOMAIN CONTROLLERS' (DC only) (Automated) ....... 66
2.3.1.3 (L1) Configure 'Accounts: Rename administrator account' (Automated) ................... 168
""".strip()
        with tempfile.TemporaryDirectory() as td:
            txt_path = os.path.join(td, "cis.txt")
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(content)
            items = parse_benchmark_txt(txt_path)
            by_code = {item["code"]: item for item in items}
            self.assertEqual(by_code["1.2.3"]["assessment"], "MS only, Manual")
            self.assertEqual(by_code["2.2.2"]["assessment"], "DC only, Automated")
            self.assertEqual(by_code["2.3.1.3"]["assessment"], "Automated")
            self.assertEqual(by_code["2.3.1.3"]["recommended"], "")
