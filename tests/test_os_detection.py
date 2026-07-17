import os
import unittest


class TestOSDetection(unittest.TestCase):
    def setUp(self):
        self._orig = os.environ.get("OS_PROFILE_OVERRIDE")

        from core.os_detection import _reset_os_cache_for_tests
        _reset_os_cache_for_tests()

    def tearDown(self):
        if self._orig is None:
            os.environ.pop("OS_PROFILE_OVERRIDE", None)
        else:
            os.environ["OS_PROFILE_OVERRIDE"] = self._orig

        from core.os_detection import _reset_os_cache_for_tests
        _reset_os_cache_for_tests()

    def test_client_win11_and_win10_supported(self):
        from core.os_detection import (
            get_os_info,
            get_server_family,
            is_client_supported,
            is_server,
        )

        for profile, expected_name in (
            ("client:win11", "Windows 11"),
            ("client:win10", "Windows 10"),
        ):
            os.environ["OS_PROFILE_OVERRIDE"] = profile
            info = get_os_info()
            self.assertEqual(info.name, expected_name)
            self.assertFalse(is_server())
            self.assertTrue(is_client_supported())
            self.assertEqual(get_server_family(), "")

    def test_client_not_misclassified_as_server_2025_on_high_build(self):
        from core.os_detection import _name_from_version, get_server_family

        self.assertEqual(_name_from_version(10, 0, 26100, 1), "Windows 11")
        os.environ["OS_PROFILE_OVERRIDE"] = "client:win11"
        self.assertEqual(get_server_family(), "")

    def test_supported_server_families(self):
        from core.os_detection import get_server_family, is_supported_server, is_server

        cases = (
            ("server:2025", "Windows Server 2025"),
            ("server:2022", "Windows Server 2022"),
            ("server:2019", "Windows Server 2019"),
            ("server:2016", "Windows Server 2016"),
            ("server:2012r2", "Windows Server 2012 R2"),
            ("server:2012", "Windows Server 2012"),
            ("server:2008r2", "Windows Server 2008 R2"),
        )
        for profile, expected_family in cases:
            os.environ["OS_PROFILE_OVERRIDE"] = profile
            self.assertTrue(is_server())
            self.assertTrue(is_supported_server())
            self.assertEqual(get_server_family(), expected_family)

    def test_legacy_win7(self):
        os.environ["OS_PROFILE_OVERRIDE"] = "legacy:win7"
        from core.os_detection import get_os_info, is_legacy

        info = get_os_info()
        self.assertEqual(info.name, "Windows 7")
        self.assertTrue(is_legacy())
