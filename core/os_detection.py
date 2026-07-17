import os
import sys
import json
import ctypes
import subprocess
from typing import Dict, Any

class OSInfo:
    def __init__(self, name: str, major: int, minor: int, build: int, product_type: int):
        self.name = name
        self.major = major
        self.minor = minor
        self.build = build
        self.product_type = product_type

_cached_info: OSInfo = None

def _env_override() -> OSInfo:
    val = os.getenv("OS_PROFILE_OVERRIDE") or ""
    val = val.strip().lower()
    if not val:
        return None
    if val.startswith("client:win11"):
        return OSInfo("Windows 11", 10, 0, 22621, 1)
    if val.startswith("client:win10"):
        return OSInfo("Windows 10", 10, 0, 19045, 1)
    if val.startswith("server:2022"):
        return OSInfo("Windows Server 2022", 10, 0, 20348, 3)
    if val.startswith("server:2025"):
        return OSInfo("Windows Server 2025", 10, 0, 26100, 3)
    if val.startswith("server:2019"):
        return OSInfo("Windows Server 2019", 10, 0, 17763, 3)
    if val.startswith("server:2016"):
        return OSInfo("Windows Server 2016", 10, 0, 14393, 3)
    if val.startswith("server:2012r2"):
        return OSInfo("Windows Server 2012 R2", 6, 3, 9600, 3)
    if val.startswith("server:2012"):
        return OSInfo("Windows Server 2012", 6, 2, 9200, 3)
    if val.startswith("server:2008r2"):
        return OSInfo("Windows Server 2008 R2", 6, 1, 7601, 3)
    if val.startswith("legacy:win7"):
        return OSInfo("Windows 7", 6, 1, 7601, 1)
    if val.startswith("legacy:xp"):
        return OSInfo("Windows XP", 5, 1, 2600, 1)
    return None


def _reset_os_cache_for_tests():
    global _cached_info
    _cached_info = None

class RTL_OSVERSIONINFOEXW(ctypes.Structure):
    _fields_ = [
        ("dwOSVersionInfoSize", ctypes.c_ulong),
        ("dwMajorVersion", ctypes.c_ulong),
        ("dwMinorVersion", ctypes.c_ulong),
        ("dwBuildNumber", ctypes.c_ulong),
        ("dwPlatformId", ctypes.c_ulong),
        ("szCSDVersion", ctypes.c_wchar * 128),
        ("wServicePackMajor", ctypes.c_ushort),
        ("wServicePackMinor", ctypes.c_ushort),
        ("wSuiteMask", ctypes.c_ushort),
        ("wProductType", ctypes.c_byte),
        ("wReserved", ctypes.c_byte),
    ]

def _fetch_via_rtl() -> Dict[str, Any]:
    try:
        info = RTL_OSVERSIONINFOEXW()
        info.dwOSVersionInfoSize = ctypes.sizeof(info)
        ntdll = ctypes.WinDLL("ntdll")
        ret = ntdll.RtlGetVersion(ctypes.byref(info))
        if ret == 0:
            return {
                "major": int(info.dwMajorVersion),
                "minor": int(info.dwMinorVersion),
                "build": int(info.dwBuildNumber),
                "product_type": int(info.wProductType),
            }
    except Exception:
        pass
    return {}

def _fetch_via_wmi() -> Dict[str, Any]:
    try:
        cmd = [
            "powershell.exe",
            "-NoProfile",
            "-Command",
            "(Get-CimInstance Win32_OperatingSystem | Select-Object Caption, Version, BuildNumber, ProductType, OSArchitecture | ConvertTo-Json)"
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5)
        if proc.returncode != 0:
            return {}
        raw = proc.stdout.strip()
        data = json.loads(raw)
        if isinstance(data, dict):
            version = str(data.get("Version") or "")
            parts = (version.split(".") + ["0", "0", "0"])[:3]
            major = int(parts[0] or 0)
            minor = int(parts[1] or 0)
            try:
                build = int((data.get("BuildNumber") or parts[2] or 0))
            except Exception:
                build = int(parts[2] or 0)
            product_type = int(data.get("ProductType") or 1)
            return {
                "major": major,
                "minor": minor,
                "build": build,
                "product_type": product_type,
                "caption": str(data.get("Caption") or ""),
                "architecture": str(data.get("OSArchitecture") or "")
            }
    except Exception:
        pass
    return {}

def _name_from_version(major: int, minor: int, build: int, product_type: int, caption: str = "") -> str:
    if major == 10:
        if build >= 22000 and product_type == 1:
            return "Windows 11"
        if product_type == 1:
            return "Windows 10"
        if build >= 26100:
            return "Windows Server 2025"
        if build >= 20348:
            return "Windows Server 2022"
        if build >= 17763:
            return "Windows Server 2019"
        if build >= 14393:
            return "Windows Server 2016"
        return caption or "Windows Server (10.x)"
    if major == 6 and minor == 1:
        return "Windows 7"
    if major == 5 and minor in (0, 1, 2):
        return "Windows XP/2003"
    if caption:
        return caption
    return f"Windows {major}.{minor}"

def get_os_info() -> OSInfo:
    global _cached_info
    override = _env_override()
    if override:
        _cached_info = override
        return _cached_info
    if _cached_info is not None:
        return _cached_info
    rtl = _fetch_via_rtl()
    data = rtl or _fetch_via_wmi()
    major = int(data.get("major") or 0)
    minor = int(data.get("minor") or 0)
    build = int(data.get("build") or 0)
    product_type = int(data.get("product_type") or 1)
    name = _name_from_version(major, minor, build, product_type, str(data.get("caption") or ""))
    _cached_info = OSInfo(name, major, minor, build, product_type)
    return _cached_info

def get_windows_edition() -> str:
    wmi = _fetch_via_wmi()
    caption = str(wmi.get("caption") or "").strip()
    lower_caption = caption.lower()
    if "home" in lower_caption:
        return "Home"
    if "pro" in lower_caption:
        return "Pro"
    if "enterprise" in lower_caption:
        return "Enterprise"
    if "education" in lower_caption:
        return "Education"
    if "datacenter" in lower_caption:
        return "Datacenter"
    if "standard" in lower_caption:
        return "Standard"
    if "server" in lower_caption:
        # preserve full caption for server names if possible
        return caption
    return caption or ""


def get_detailed_os_info() -> Dict[str, Any]:
    info = get_os_info()
    detailed = {
        "name": info.name,
        "version": f"{info.major}.{info.minor}",
        "build": info.build,
        "product_type": info.product_type,
        "architecture": "",
        "edition": get_windows_edition(),
    }
    wmi = _fetch_via_wmi()
    arch = (wmi.get("architecture") or "").strip()
    if not arch:
        try:
            import platform
            arch = platform.machine() or ""
        except Exception:
            arch = ""
    detailed["architecture"] = arch
    return detailed


def get_server_family() -> str:
    info = get_os_info()
    # Guard rail: never classify workstation/client SKU as a Server family.
    if info.product_type == 1:
        return ""
    if info.major == 10 and info.build >= 26100:
        return "Windows Server 2025"
    if info.major == 10 and info.build >= 20348:
        return "Windows Server 2022"
    if info.major == 10 and info.build >= 17763:
        return "Windows Server 2019"
    if info.major == 10 and info.build >= 14393:
        return "Windows Server 2016"
    if info.major == 6 and info.minor == 3:
        return "Windows Server 2012 R2"
    if info.major == 6 and info.minor == 2:
        return "Windows Server 2012"
    if info.major == 6 and info.minor == 1:
        return "Windows Server 2008 R2"
    return info.name if info.product_type != 1 else ""


def is_server() -> bool:
    info = get_os_info()
    return info.product_type != 1


def is_supported_server() -> bool:
    if not is_server():
        return False
    family = get_server_family()
    return family in {
        "Windows Server 2025",
        "Windows Server 2022",
        "Windows Server 2019",
        "Windows Server 2016",
        "Windows Server 2012 R2",
        "Windows Server 2012",
        "Windows Server 2008 R2",
    }


def is_windows_client_home_or_pro() -> bool:
    info = get_os_info()
    if info.product_type != 1:
        return False
    edition = get_windows_edition().lower()
    return edition in {"home", "pro"}


def is_client_supported() -> bool:
    info = get_os_info()
    if info.product_type != 1:
        return False
    if info.major == 10:
        return True
    return False


def is_os_supported() -> bool:
    return is_supported_server() or is_client_supported()

def is_legacy() -> bool:
    info = get_os_info()
    if info.major < 6:
        return True
    if info.major == 6 and info.minor <= 1:
        return True
    return False

def show_legacy_block_and_exit(app):
    from PyQt5.QtWidgets import QMessageBox
    from PyQt5.QtCore import QTimer
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Warning)
    msg.setWindowTitle("版本不支援")
    msg.setText("您的 Windows 版本過低，無法運行本程式")
    msg.setStandardButtons(QMessageBox.Ok)
    msg.setModal(True)
    QTimer.singleShot(5000, lambda: (msg.close(), sys.exit(0)))
    msg.exec_()
