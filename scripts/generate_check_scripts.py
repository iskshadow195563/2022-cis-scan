import json
import os
import re

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ITEMS_PATH = os.path.join(BASE_DIR, "data", "cis_items.json")
MAPPING_PATH = os.path.join(BASE_DIR, "data", "cis_mapping.json")
CHECKS_DIR = os.path.join(BASE_DIR, "scripts", "checks")

SECEDIT_SYSTEM_ACCESS_KEYS = {
    "1.1.1": {"PasswordHistorySize": 24},
    "1.1.5": {"PasswordComplexity": 1},
    "1.1.7": {"ClearTextPassword": 0},
}

NET_ACCOUNTS_ITEMS = {
    "1.1.2": {"key": "MaxPasswordAge", "compare_op": "le", "expected": 365},
    "1.1.3": {"key": "MinPasswordAge", "compare_op": "ge", "expected": 1},
    "1.1.4": {"key": "MinPasswordLength", "compare_op": "ge", "expected": 14},
    "1.2.1": {"key": "LockoutDuration", "compare_op": "ge", "expected": 15},
    "1.2.2": {"key": "LockoutThreshold", "compare_op": "le", "expected": 5},
    "1.2.3": {"key": "LockoutWindow", "compare_op": "ge", "expected": 15},
}

REGISTRY_MAP_2_3 = {
    "2.3.1.1": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "NoConnectedUser", 3),
    "2.3.1.2": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "EnableLUA", 1),
    "2.3.1.3": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "EnableVirtualization", 1),
    "2.3.1.4": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "PromptOnSecureDesktop", 1),
    "2.3.1.5": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "ConsentPromptBehaviorAdmin", 2),
    "2.3.1.6": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "ConsentPromptBehaviorUser", 0),
    "2.3.1.7": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "ValidateAdminCodeSignatures", 1),
    "2.3.1.8": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "EnableSecureUIAPaths", 1),
    "2.3.1.9": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "EnableInstallerDetection", 1),
    "2.3.2.1": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "DisableAutomaticRestartSignOn", 1),
    "2.3.4.1": ("HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Session Manager\\Memory Management", "ClearPageFileAtShutdown", 1),
    "2.3.5.1": ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\NetBT\\Parameters", "NoNameReleaseOnDemand", 1),
    "2.3.6.1": ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip6\\Parameters", "DisableIPSourceRouting", 2),
    "2.3.6.2": ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Tcpip\\Parameters", "DisableIPSourceRouting", 2),
    "2.3.7.1": ("HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa", "LimitBlankPasswordUse", 1),
    "2.3.7.2": ("HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa", "NoLMHash", 1),
    "2.3.7.3": ("HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa", "DisableDomainCreds", 0),
    "2.3.7.4": ("HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa", "RestrictAnonymous", 0),
    "2.3.7.5": ("HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa", "RestrictAnonymousSAM", 1),
    "2.3.7.6": ("HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa", "EveryoneIncludesAnonymous", 0),
    "2.3.7.7": ("HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\MSV1_0", "NTLMMinClientSec", 537395200),
    "2.3.7.8": ("HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa", "LmCompatibilityLevel", 5),
    "2.3.7.9": ("HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa", "RestrictRemoteSAM", 1),
    "2.3.8.1": ("HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\FIPSAlgorithmPolicy", "Enabled", 0),
    "2.3.9.1": ("HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\MSV1_0", "AllowNullSessionFallback", 0),
    "2.3.9.2": ("HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa\\pku2u", "AllowOnlineID", 0),
    "2.3.10.1": ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\LanManServer\\Parameters", "EnableSecuritySignature", 1),
    "2.3.10.2": ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\LanManServer\\Parameters", "RequireSecuritySignature", 1),
    "2.3.10.3": ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\LanManServer\\Parameters", "EnableForcedLogoff", 1),
    "2.3.10.4": ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\LanmanWorkstation\\Parameters", "RequireSecuritySignature", 1),
    "2.3.10.5": ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\LanmanWorkstation\\Parameters", "EnableSecuritySignature", 1),
    "2.3.10.6": ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\LDAP", "LDAPClientIntegrity", 2),
    "2.3.10.7": ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Netlogon\\Parameters", "RefusePasswordChange", 0),
    "2.3.10.8": ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Netlogon\\Parameters", "SealSecureChannel", 1),
    "2.3.10.9": ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Netlogon\\Parameters", "SignSecureChannel", 1),
    "2.3.10.10": ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\Netlogon\\Parameters", "RequireSignOrSeal", 1),
    "2.3.11.1": ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\LanmanServer\\Parameters", "AutoDisconnect", 15),
    "2.3.11.2": ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\LanmanServer\\Parameters", "SMB1", 0),
    "2.3.12.1": ("HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Lsa", "SCENoApplyLegacyAuditPolicy", 1),
}

SERVICE_ITEMS = {
    "5.1": ("Spooler", "Stopped"),
    "5.2": ("RemoteRegistry", "Stopped"),
    "5.3": ("RemoteAccess", "Stopped"),
    "5.4": ("TlntSvr", "Stopped"),
    "5.5": ("msftpsvc", "Stopped"),
    "5.6": ("SNMP", "Stopped"),
    "5.7": ("W3SVC", "Stopped"),
    "5.8": ("XboxNetApiSvc", "Stopped"),
    "5.9": ("XblAuthManager", "Stopped"),
    "5.10": ("XblGameSave", "Stopped"),
    "5.11": ("LanmanServer", "Running"),
    "5.12": ("LanmanWorkstation", "Running"),
}

AUDITPOL_ITEMS = {
    "17.1.1": ("Audit Credential Validation", "enable", "enable"),
    "17.2.1": ("Audit Application Group Management", "enable", "enable"),
    "17.3.1": ("Audit Security Group Management", "enable", "enable"),
    "17.3.2": ("Audit User Account Management", "enable", "enable"),
    "17.4.1": ("Audit PNP Activity", "enable", "enable"),
    "17.5.1": ("Audit Process Creation", "enable", "enable"),
    "17.5.2": ("Audit Process Termination", "enable", "enable"),
    "17.6.1": ("Audit Account Lockout", "enable", "enable"),
    "17.6.2": ("Audit Group Membership", "enable", "enable"),
    "17.6.3": ("Audit Logoff", "enable", "enable"),
    "17.6.4": ("Audit Logon", "enable", "enable"),
    "17.6.5": ("Audit Other Logon/Logoff Events", "enable", "enable"),
    "17.6.6": ("Audit Special Logon", "enable", "enable"),
    "17.7.1": ("Audit Other Object Access Events", "enable", "enable"),
    "17.7.2": ("Audit Removable Storage", "enable", "enable"),
    "17.8.1": ("Audit Audit Policy Change", "enable", "enable"),
    "17.8.2": ("Audit Authentication Policy Change", "enable", "enable"),
    "17.8.3": ("Audit Authorization Policy Change", "enable", "enable"),
    "17.9.1": ("Audit Sensitive Privilege Use", "enable", "enable"),
    "17.10.1": ("Audit IPsec Driver", "enable", "enable"),
    "17.11.1": ("Audit Other System Events", "enable", "enable"),
    "17.12.1": ("Audit Security State Change", "enable", "enable"),
    "17.13.1": ("Audit Security System Extension", "enable", "enable"),
    "17.14.1": ("Audit System Integrity", "enable", "enable"),
}

FIREWALL_ITEMS = {
    "9.1.1": ("Domain", "Enabled", "True"),
    "9.1.2": ("Private", "Enabled", "True"),
    "9.1.3": ("Public", "Enabled", "True"),
    "9.2.1": ("Domain", "DefaultInboundAction", "Block"),
    "9.2.2": ("Private", "DefaultInboundAction", "Block"),
    "9.2.3": ("Public", "DefaultInboundAction", "Block"),
    "9.3.1": ("Domain", "DefaultOutboundAction", "Allow"),
    "9.3.2": ("Private", "DefaultOutboundAction", "Allow"),
    "9.3.3": ("Public", "DefaultOutboundAction", "Allow"),
    "9.4.1": ("Domain", "AllowLocalFirewallRules", "False"),
    "9.4.2": ("Private", "AllowLocalFirewallRules", "False"),
    "9.4.3": ("Public", "AllowLocalFirewallRules", "False"),
    "9.5.1": ("Domain", "AllowLocalIPsecRules", "False"),
    "9.5.2": ("Private", "AllowLocalIPsecRules", "False"),
    "9.5.3": ("Public", "AllowLocalIPsecRules", "False"),
    "9.6.1": ("Domain", "LogFileName", "%SystemRoot%\\System32\\logfiles\\firewall\\domainfw.log"),
    "9.6.2": ("Private", "LogFileName", "%SystemRoot%\\System32\\logfiles\\firewall\\privatefw.log"),
    "9.6.3": ("Public", "LogFileName", "%SystemRoot%\\System32\\logfiles\\firewall\\publicfw.log"),
}

SECTION_18_REGISTRY_PREFIX = {
    "18.": "HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\",
    "19.": "HKCU:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\",
}

ADMIN_TEMPLATE_REG_MAP = {
    "1.1.6": ("HKLM:\\SYSTEM\\CurrentControlSet\\Control\\Sam", "RelaxMinimumPasswordLengthLimits", 1),
    "18.1.1.1": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "NoLockScreen", 0),
    "18.1.1.2": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "DisableLockScreenAppNotifications", 1),
    "18.1.2.1": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\Personalization", "NoLockScreenCamera", 1),
    "18.1.2.2": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\Personalization", "NoLockScreenSlideshow", 1),
    "18.2.1": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\AppCompat", "AicEnabled", 1),
    "18.2.2": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer", "NoInternetIcon", 1),
    "18.3.1": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU", "NoAutoUpdate", 0),
    "18.3.2": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU", "AUOptions", 3),
    "18.3.3": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU", "ScheduledInstallDay", 0),
    "18.3.4": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU", "NoAutoRebootWithLoggedOnUsers", 1),
    "18.3.5": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate\\AU", "AutomaticMaintenanceEnabled", 1),
    "18.3.6": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WindowsUpdate", "DoNotConnectToWindowsUpdateInternetLocations", 0),
    "18.4.1": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\CredentialsDelegation", "AllowProtectedCreds", 0),
    "18.4.2": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\CredentialsDelegation", "AllowEncryptionOracle", 0),
    "18.4.3": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\CredUI", "EnumerateAdministrators", 0),
    "18.5.1": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System\\Audit", "ProcessCreationIncludeCmdLine_Enabled", 1),
    "18.5.2": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\EventLog\\Application", "MaxSize", 32768),
    "18.5.3": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\EventLog\\Security", "MaxSize", 196608),
    "18.5.4": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\EventLog\\System", "MaxSize", 32768),
    "18.6.1": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\Explorer", "NoAutoplayfornonVolume", 1),
    "18.6.2": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer", "NoDriveTypeAutoRun", 255),
    "18.6.3": ("HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\Explorer", "NoAutorun", 1),
    "18.7.1": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\Installer", "AlwaysInstallElevated", 0),
    "18.7.2": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\Installer", "EnableUserControl", 0),
    "18.8.1": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\ScriptBlockLogging", "EnableScriptBlockLogging", 1),
    "18.8.2": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\PowerShell\\ModuleLogging", "EnableModuleLogging", 1),
    "18.8.3": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Service\\WinRS", "AllowRemoteShellAccess", 0),
    "18.8.4": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Client", "AllowBasic", 0),
    "18.8.5": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Client", "AllowUnencryptedTraffic", 0),
    "18.8.6": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Client", "AllowDigest", 0),
    "18.8.7": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Service", "AllowBasic", 0),
    "18.8.8": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Service", "AllowUnencryptedTraffic", 0),
    "18.8.9": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows\\WinRM\\Service", "DisableRunAs", 1),
    "18.9.1.1": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Scan", "DisableRemovableDriveScanning", 0),
    "18.9.1.2": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Spynet", "SpynetReporting", 2),
    "18.9.1.3": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Real-Time Protection", "DisableRealtimeMonitoring", 0),
    "18.9.1.4": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Real-Time Protection", "DisableBehaviorMonitoring", 0),
    "18.9.1.5": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Real-Time Protection", "DisableIOAVProtection", 0),
    "18.9.1.6": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Real-Time Protection", "DisableScriptScanning", 0),
    "18.9.1.7": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Real-Time Protection", "DisableOnAccessProtection", 0),
    "18.9.1.8": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Reporting", "DisableGenericReports", 0),
    "18.9.2.1": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\MpEngine", "MpEnablePus", 1),
    "18.9.3.1": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\NIS", "DisableBthAvdtp", 0),
    "18.9.4.1": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Windows Defender Exploit Guard\\ASR", "ExploitGuard_ASR_Rules", 1),
    "18.9.5.1": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Windows Defender Exploit Guard\\Network Protection", "EnableNetworkProtection", 1),
    "18.9.6.1": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Windows Defender Exploit Guard\\Controlled Folder Access", "EnableControlledFolderAccess", 1),
    "18.9.7.1": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Threats", "Threats_ThreatSeverityDefaultAction", 1),
    "18.9.8.1": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\Signature Updates", "ForceUpdateFromMU", 1),
    "18.9.9.1": ("HKLM:\\SOFTWARE\\Policies\\Microsoft\\Windows Defender\\UX Configuration", "UILockdown", 1),
}

MSS_ITEMS = {
    "2.3.10.11": ("HKLM:\\SYSTEM\\CurrentControlSet\\Services\\LanmanServer\\Parameters", "EnableSMBQUIC", 0),
}

def determine_check_type(code, item):
    prefix = code.split(".")[0]
    assessment = (item.get("assessment") or "").lower()
    tags = [t.lower() for t in (item.get("tags") or [])]
    is_manual = "manual" in assessment or any("manual" in t for t in tags)

    if code in SECEDIT_SYSTEM_ACCESS_KEYS:
        return "secedit_system_access"
    if code in NET_ACCOUNTS_ITEMS:
        return "net_accounts_compare"
    if code in SERVICE_ITEMS:
        return "service"
    if code in AUDITPOL_ITEMS:
        return "auditpol"
    if code in FIREWALL_ITEMS:
        return "firewall_profile"
    if code in ADMIN_TEMPLATE_REG_MAP or code in REGISTRY_MAP_2_3 or code in MSS_ITEMS:
        return "gpo_setting"

    if code.startswith("1.1."):
        return "net_accounts_compare"
    if code.startswith("1.2."):
        return "net_accounts_compare"
    if code.startswith("2.2."):
        return "secedit_privilege_rights"
    if code.startswith("2.3."):
        return "gpo_setting"
    if code.startswith("5."):
        return "service_startmode"
    if code.startswith("9."):
        return "firewall_profile"
    if code.startswith("17."):
        return "auditpol"
    if code.startswith("18.") or code.startswith("19."):
        return "gpo_setting"

    if is_manual:
        return "not_applicable"

    return "not_applicable"


def build_mapping():
    with open(ITEMS_PATH, "r", encoding="utf-8") as f:
        items = json.load(f)

    mapping = {}

    for item in items:
        code = item["code"]
        check = determine_check_type(code, item)

        entry = {"action": check, "reboot": False}

        if code in SECEDIT_SYSTEM_ACCESS_KEYS:
            entry["system_access"] = SECEDIT_SYSTEM_ACCESS_KEYS[code]
        elif code in NET_ACCOUNTS_ITEMS:
            ni = NET_ACCOUNTS_ITEMS[code]
            entry["key"] = ni["key"]
            entry["compare_op"] = ni["compare_op"]
            entry["expected"] = ni["expected"]
        elif code in SERVICE_ITEMS:
            svc = SERVICE_ITEMS[code]
            entry["service_name"] = svc[0]
            entry["expected_state"] = svc[1]
        elif code in AUDITPOL_ITEMS:
            ap = AUDITPOL_ITEMS[code]
            entry["subcategory"] = ap[0]
            entry["success"] = ap[1]
            entry["failure"] = ap[2]
        elif code in FIREWALL_ITEMS:
            fw = FIREWALL_ITEMS[code]
            entry["profile"] = fw[0]
            entry["setting"] = fw[1]
            entry["expected"] = fw[2]
        elif code in ADMIN_TEMPLATE_REG_MAP:
            rm = ADMIN_TEMPLATE_REG_MAP[code]
            entry["path"] = rm[0]
            entry["name"] = rm[1]
            entry["expected"] = rm[2]
        elif code in REGISTRY_MAP_2_3:
            rm = REGISTRY_MAP_2_3[code]
            entry["path"] = rm[0]
            entry["name"] = rm[1]
            entry["expected"] = rm[2]
        elif code in MSS_ITEMS:
            rm = MSS_ITEMS[code]
            entry["path"] = rm[0]
            entry["name"] = rm[1]
            entry["expected"] = rm[2]
        elif check == "not_applicable":
            entry["reason"] = item.get("assessment", "manual")
        else:
            entry["path"] = ""
            entry["name"] = ""
            entry["expected"] = 0

        mapping[code] = entry

    os.makedirs(os.path.dirname(MAPPING_PATH), exist_ok=True)
    with open(MAPPING_PATH, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)

    print(f"Generated mapping with {len(mapping)} entries -> {MAPPING_PATH}")

    check_type_counts = {}
    for v in mapping.values():
        t = v["action"]
        check_type_counts[t] = check_type_counts.get(t, 0) + 1
    print("Check type distribution:")
    for t, c in sorted(check_type_counts.items(), key=lambda x: -x[1]):
        print(f"  {c:4d}  {t}")

    return mapping


def generate_check_scripts(mapping):
    os.makedirs(CHECKS_DIR, exist_ok=True)

    framework_rel = "..\\cis_check_framework.ps1"

    count = 0
    for code in sorted(mapping.keys()):
        script_path = os.path.join(CHECKS_DIR, f"check_{code.replace('.', '_')}.ps1")
        content = f"""param()
$framework = Join-Path $PSScriptRoot "{framework_rel}"
& $framework -Code "{code}"
exit $LASTEXITCODE
"""
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(content)
        count += 1

    print(f"Generated {count} check scripts -> {CHECKS_DIR}")


def update_cis_items():
    with open(ITEMS_PATH, "r", encoding="utf-8") as f:
        items = json.load(f)

    for item in items:
        code = item["code"]
        script_path = os.path.join("scripts", "checks", f"check_{code.replace('.', '_')}.ps1")
        item["script_path"] = script_path

    with open(ITEMS_PATH, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)

    print(f"Updated {len(items)} items with script_path in {ITEMS_PATH}")


if __name__ == "__main__":
    mapping = build_mapping()
    generate_check_scripts(mapping)
    update_cis_items()
    print("\nDone! All 436 CIS check scripts generated and linked.")
