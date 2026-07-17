import json
import re

def check_untranslated():
    with open('data/cis_items.zh_hk.json', 'r', encoding='utf-8') as f:
        data = json.load(f)

    english_pattern = re.compile(r'[a-zA-Z]{3,}')
    untranslated = []

    # Words to ignore (Proper nouns, acronyms, technical terms kept in English)
    ignored_words = {
        'MS', 'DC', 'RDP', 'NT', 'VM', 'IIS_IUSRS', 'WdiServiceHost', 'SERVICE',
        'LDAP', 'Netlogon', 'Kerberos', 'NTLM', 'NTLMv2', 'LM', 'SMB',
        'Windows', 'Microsoft',
        'AES128_HMAC_SHA1', 'AES256_HMAC_SHA1',
        'SEHOP', 'WDigest', 'MPSSVC', 'PNP', 'IPsec',
        'SAM', 'SID', 'PKU2U', 'LAN', 'Manager', 'SSP',
        'CTRL', 'ALT', 'DEL',
        'SPN', 'NetBT', 'NodeType',
        'AutoAdminLogon', 'RSPNDR',
        'Everyone', 'IUSRS', 'IIS', 'WdiServiceHost',
        'LSA', 'UEFI', 'DMA', 'BitLocker', 'SmartScreen', 'PowerShell', 'WinRM',
        'TCPIP', 'IPv6', 'IPv4', 'DNS', 'DHCP', 'WINS',
        'S-1-5-32-544', 'S-1-5-32-545', # SIDs
        'Administrators', 'Guests', 'Users', # Should be translated, but if found, flag them.
        'LLTDIO', 'RSPNDR', 'mDNS', 'NetBIOS', 'IPv6', 'IPv', 'IRDP', 'ICMP', 'UAC', 'MSS',
        'DisableIPSourceRouting', 'EnableICMPRedirect', 'NoNameReleaseOnDemand', 'SafeDllSearchMode',
        'ScreenSaverGracePeriod', 'WarningLevel', 'KeepAliveTime', 'PerformRouterDiscovery',
        'TcpMaxDataRetransmissions', 'SystemRoot', 'System', 'logfiles', 'firewall', 'publicfw', 'log',
        'LocalSystem', 'PKU', 'AES', 'HMAC', 'SHA', 'NTLMv', 'UIAccess', 'domainfw', 'privatefw', 'One',
        'DLL', 'Responder'
    }

    for code, item in data.items():
        desc = item['description']
        # Find English words
        words = english_pattern.findall(desc)
        # Filter out ignored words
        real_english = [w for w in words if w not in ignored_words]

        if real_english:
            untranslated.append(f"{code}: {desc} -> Found: {real_english}")

    print(f"Found {len(untranslated)} potentially untranslated items.")
    for item in untranslated:
        print(item)

if __name__ == "__main__":
    check_untranslated()
