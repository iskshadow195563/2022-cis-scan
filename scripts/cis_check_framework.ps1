param(
    [Parameter(Mandatory=$true)]
    [string]$Code,
    [string]$MappingPath = "",
    [string]$MappingJson = ""
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($MappingPath) -and [string]::IsNullOrWhiteSpace($MappingJson)) {
    $scriptRoot = $PSScriptRoot
    if ([string]::IsNullOrWhiteSpace($scriptRoot) -and $MyInvocation.MyCommand.Path) {
        $scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    $MappingPath = Join-Path (Split-Path -Parent $scriptRoot) "data\cis_mapping.json"
}

function Write-CisDebug {
    param([string]$Message)
    $ts = (Get-Date).ToString("yyyy-MM-dd HH:mm:ss.fff")
    Write-Host "[CIS_DEBUG $ts] $Message"
}

function Write-CisResult {
    param([string]$Status, [string]$Detail, [string]$Actual)
    $obj = [PSCustomObject]@{
        Code   = $Code
        Status = $Status
        Detail = $Detail
    }
    if ($Actual) { $obj | Add-Member -NotePropertyName Actual -NotePropertyValue $Actual }
    Write-Output ($obj | ConvertTo-Json -Compress)
}

function Get-CheckMapping {
    param([string]$Code)
    if ($MappingJson -and $MappingJson.Trim()) {
        $map = $MappingJson | ConvertFrom-Json
    } else {
        if (-not (Test-Path $MappingPath)) {
            Write-CisResult -Status "ERROR" -Detail "Mapping file not found: $MappingPath"
            exit 1
        }
        $map = Get-Content -Raw -Path $MappingPath | ConvertFrom-Json
    }
    $entry = $map.$Code
    if (-not $entry) {
        Write-CisResult -Status "ERROR" -Detail "No mapping for code: $Code"
        exit 1
    }
    return $entry
}

function Test-TextValue {
    param($Value)
    return -not [string]::IsNullOrWhiteSpace([string]$Value)
}

function Normalize-RegistryPath {
    param([string]$Path)
    if (-not (Test-TextValue $Path)) { return "" }
    $p = $Path.Trim()
    $roots = @("HKLM", "HKCU", "HKU", "HKCR")
    foreach ($root in $roots) {
        $prefix = "$root`:"
        $prefixSlash = "$root`:\"
        if ($p.StartsWith($prefixSlash, [StringComparison]::OrdinalIgnoreCase)) {
            return $p
        }
        if ($p.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
            $suffix = $p.Substring($prefix.Length).TrimStart([char]'\')
            return "$prefixSlash$suffix"
        }
    }
    return $p
}

function Check-NetAccounts {
    param([hashtable]$Expected)
    $out = cmd.exe /c "net accounts" 2>&1
    $actual = @{}
    foreach ($line in $out) {
        $t = $line.Trim()
        if ($t -match "Maximum password age.*:\s*(\d+)")         { $actual["MaxPasswordAge"] = $matches[1] }
        elseif ($t -match "Minimum password age.*:\s*(\d+)")     { $actual["MinPasswordAge"] = $matches[1] }
        elseif ($t -match "Minimum password length.*:\s*(\d+)")  { $actual["MinPasswordLength"] = $matches[1] }
        elseif ($t -match "Lockout threshold.*:\s*(\d+)")        { $actual["LockoutThreshold"] = $matches[1] }
        elseif ($t -match "Lockout duration.*:\s*(\d+)")         { $actual["LockoutDuration"] = $matches[1] }
        elseif ($t -match "Reset lockout counter after.*:\s*(\d+)") { $actual["LockoutWindow"] = $matches[1] }
    }
    $matches_all = $true
    foreach ($key in $Expected.Keys) {
        if (-not $actual.ContainsKey($key) -or $actual[$key] -ne $Expected[$key]) {
            $matches_all = $false
            break
        }
    }
    if ($matches_all) {
        Write-CisResult -Status "PASS" -Detail "compliant" -Actual ($actual | ConvertTo-Json -Compress)
        exit 0
    } else {
        Write-CisResult -Status "FAIL" -Detail "noncompliant" -Actual ($actual | ConvertTo-Json -Compress)
        exit 1
    }
}

function Check-SeceditSystemAccess {
    param([hashtable]$Expected)
    $values = Get-SeceditSystemAccessValues
    Write-CisDebug "Check-SeceditSystemAccess: expected_keys=$($Expected.Keys -join ',') found_keys=$($values.Keys -join ',')"
    $matches_all = $true
    foreach ($key in $Expected.Keys) {
        $actual_val = if ($values.ContainsKey($key)) { $values[$key] } else { "" }
        $expected_val = [string]$Expected[$key]
        Write-CisDebug "Check-SeceditSystemAccess: key=$key actual=$actual_val expected=$expected_val"
        if ($actual_val -ne $expected_val) {
            $matches_all = $false
            break
        }
    }
    if ($matches_all) {
        Write-CisResult -Status "PASS" -Detail "compliant" -Actual ($values | ConvertTo-Json -Compress)
        exit 0
    } else {
        Write-CisResult -Status "FAIL" -Detail "noncompliant" -Actual ($values | ConvertTo-Json -Compress)
        exit 1
    }
}

function Get-SeceditSystemAccessValues {
    $tmp = [IO.Path]::GetTempFileName()
    secedit /export /cfg $tmp 2>&1 | Out-Null
    Write-CisDebug "Get-SeceditSystemAccessValues: secedit /export /cfg $tmp"

    $values = @{}
    if (Test-Path $tmp) {
        $lines = Get-Content $tmp
        $inSection = $false
        foreach ($line in $lines) {
            $t = $line.Trim()
            if ($t -eq "[System Access]") { $inSection = $true; continue }
            if ($t.StartsWith("[")) { $inSection = $false }
            if (-not $inSection -or -not $t) { continue }
            if ($t -match "^(\w+)\s*=\s*(.+)$") {
                $values[$matches[1]] = $matches[2].Trim()
            }
        }
        Remove-Item $tmp -Force
    }

    return $values
}

function Check-SeceditPrivilegeRights {
    param([string]$PrivilegeName, [string]$ExpectedSIDList)
    if (-not (Test-TextValue $PrivilegeName)) {
        Write-CisResult -Status "UNSUPPORTED" -Detail "mapping_missing_privilege_name" -Actual ""
        exit 0
    }
    $tmp = [IO.Path]::GetTempFileName()
    secedit /export /cfg $tmp | Out-Null
    $actual = ""
    if (Test-Path $tmp) {
        $lines = Get-Content $tmp
        $inSection = $false
        foreach ($line in $lines) {
            $t = $line.Trim()
            if ($t -eq "[Privilege Rights]") { $inSection = $true; continue }
            if ($t.StartsWith("[")) { $inSection = $false }
            if (-not $inSection -or -not $t) { continue }
            if ($t -match "^$([Regex]::Escape($PrivilegeName))\s*=\s*(.+)$") {
                $actual = $matches[1].Trim()
                break
            }
        }
        Remove-Item $tmp -Force
    }
    if (-not $actual) {
        Write-CisResult -Status "FAIL" -Detail "privilege_not_found" -Actual ""
        exit 1
    }
    $actual_set = @($actual -split ',' | ForEach-Object { ($_ -replace '\*','').Trim() } | Where-Object { $_ })
    $expected_set = @($ExpectedSIDList -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
    $missing = $expected_set | Where-Object { $_ -notin $actual_set }
    $extra = $actual_set | Where-Object { $_ -notin $expected_set }
    if ($missing.Count -eq 0 -and $extra.Count -eq 0) {
        Write-CisResult -Status "PASS" -Detail "compliant" -Actual $actual
        exit 0
    } else {
        Write-CisResult -Status "FAIL" -Detail "noncompliant" -Actual $actual
        exit 1
    }
}

function Check-RegistryValue {
    param([string]$Path, [string]$Name, $Expected, [string]$CompareOp = "eq")
    if (-not (Test-TextValue $Path) -or -not (Test-TextValue $Name)) {
        Write-CisResult -Status "UNSUPPORTED" -Detail "mapping_missing_registry_path_or_name" -Actual ""
        exit 0
    }
    $reg_path = Normalize-RegistryPath -Path $Path
    if (-not (Test-Path $reg_path)) {
        Write-CisResult -Status "FAIL" -Detail "registry_path_not_found" -Actual ""
        exit 1
    }
    $item = Get-ItemProperty -Path $reg_path -Name $Name -ErrorAction SilentlyContinue
    if (-not $item -or $null -eq $item.$Name) {
        Write-CisResult -Status "FAIL" -Detail "registry_value_not_found" -Actual ""
        exit 1
    }
    $actual = $item.$Name
    $ok = $false
    switch ($CompareOp) {
        "eq"  { $ok = [string]$actual -eq [string]$Expected }
        "ne"  { $ok = [string]$actual -ne [string]$Expected }
        "ge"  { $ok = [int]$actual -ge [int]$Expected }
        "le"  { $ok = [int]$actual -le [int]$Expected }
        "gt"  { $ok = [int]$actual -gt [int]$Expected }
        "lt"  { $ok = [int]$actual -lt [int]$Expected }
        "contains" { $ok = [string]$actual -like "*$Expected*" }
        default { $ok = [string]$actual -eq [string]$Expected }
    }
    if ($ok) {
        Write-CisResult -Status "PASS" -Detail "compliant" -Actual $actual
        exit 0
    } else {
        Write-CisResult -Status "FAIL" -Detail "noncompliant" -Actual $actual
        exit 1
    }
}

function Check-RegistryExists {
    param([string]$Path)
    if (-not (Test-TextValue $Path)) {
        Write-CisResult -Status "UNSUPPORTED" -Detail "mapping_missing_registry_path" -Actual ""
        exit 0
    }
    $reg_path = Normalize-RegistryPath -Path $Path
    if (Test-Path $reg_path) {
        Write-CisResult -Status "PASS" -Detail "compliant" -Actual "exists"
        exit 0
    } else {
        Write-CisResult -Status "FAIL" -Detail "noncompliant" -Actual "not_found"
        exit 1
    }
}

function Check-Service {
    param([string]$ServiceName, [string]$ExpectedState)
    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $svc) {
        Write-CisResult -Status "FAIL" -Detail "service_not_found" -Actual ""
        exit 1
    }
    $actual = $svc.Status.ToString()
    if ($actual -eq $ExpectedState) {
        Write-CisResult -Status "PASS" -Detail "compliant" -Actual $actual
        exit 0
    } else {
        Write-CisResult -Status "FAIL" -Detail "noncompliant" -Actual $actual
        exit 1
    }
}

function Check-ServiceStartMode {
    param([string]$ServiceName, [string]$ExpectedMode)
    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if (-not $svc) {
        Write-CisResult -Status "FAIL" -Detail "service_not_found" -Actual ""
        exit 1
    }
    $actual = $svc.StartType.ToString()
    if ($actual -eq $ExpectedMode) {
        Write-CisResult -Status "PASS" -Detail "compliant" -Actual $actual
        exit 0
    } else {
        Write-CisResult -Status "FAIL" -Detail "noncompliant" -Actual $actual
        exit 1
    }
}

function Check-AuditPol {
    param([string]$Subcategory, [string]$Success, [string]$Failure)
    if (-not (Test-TextValue $Subcategory)) {
        Write-CisResult -Status "UNSUPPORTED" -Detail "mapping_missing_auditpol_subcategory" -Actual ""
        exit 0
    }

    $candidates = @($Subcategory)
    if ($Subcategory -match "^Audit\s+(.+)$") {
        $candidates += $matches[1]
    }

    $setting = ""
    $matchedName = ""
    $rawOutput = ""
    foreach ($candidate in ($candidates | Select-Object -Unique)) {
        $out = auditpol /get /subcategory:"$candidate" 2>&1 | Out-String
        $rawOutput = $out
        foreach ($line in ($out -split "`r?`n")) {
            $t = $line.Trim()
            if (-not $t) { continue }
            if ($t -match "^(?<name>.+?)\s{2,}(?<setting>No Auditing|Success and Failure|Success|Failure)$") {
                $matchedName = $matches["name"].Trim()
                $setting = $matches["setting"].Trim()
                break
            }
        }
        if ($setting) { break }
    }

    if (-not $setting) {
        Write-CisResult -Status "FAIL" -Detail "auditpol_subcategory_not_found" -Actual ($rawOutput.Trim())
        exit 1
    }

    $settingLower = $setting.ToLowerInvariant()
    $actual_success_enabled = $settingLower.Contains("success")
    $actual_failure_enabled = $settingLower.Contains("failure")
    $actual = "$matchedName = $setting"

    $success_expected = ([string]$Success).Trim().ToLowerInvariant()
    $failure_expected = ([string]$Failure).Trim().ToLowerInvariant()
    $success_ok = ($success_expected -in @("", "any")) -or (($success_expected -in @("enable", "enabled", "true", "yes", "success")) -and $actual_success_enabled) -or (($success_expected -in @("disable", "disabled", "false", "no")) -and -not $actual_success_enabled)
    $failure_ok = ($failure_expected -in @("", "any")) -or (($failure_expected -in @("enable", "enabled", "true", "yes", "failure")) -and $actual_failure_enabled) -or (($failure_expected -in @("disable", "disabled", "false", "no")) -and -not $actual_failure_enabled)
    if ($success_ok -and $failure_ok) {
        Write-CisResult -Status "PASS" -Detail "compliant" -Actual $actual
        exit 0
    } else {
        Write-CisResult -Status "FAIL" -Detail "noncompliant" -Actual $actual
        exit 1
    }
}

function Check-FirewallProfile {
    param([string]$Profile, [string]$Setting, [string]$Expected)
    $fw = Get-NetFirewallProfile -Name $Profile -ErrorAction SilentlyContinue
    if (-not $fw) {
        Write-CisResult -Status "FAIL" -Detail "profile_not_found" -Actual ""
        exit 1
    }
    $actual = $fw.$Setting
    if ([string]$actual -eq [string]$Expected) {
        Write-CisResult -Status "PASS" -Detail "compliant" -Actual $actual
        exit 0
    } else {
        Write-CisResult -Status "FAIL" -Detail "noncompliant" -Actual $actual
        exit 1
    }
}

function Check-FirewallRule {
    param([string]$DisplayName, [string]$ExpectedEnabled)
    $rule = Get-NetFirewallRule -DisplayName $DisplayName -ErrorAction SilentlyContinue
    if (-not $rule) {
        Write-CisResult -Status "FAIL" -Detail "rule_not_found" -Actual ""
        exit 1
    }
    $actual = $rule.Enabled.ToString()
    if ($actual -eq $ExpectedEnabled) {
        Write-CisResult -Status "PASS" -Detail "compliant" -Actual $actual
        exit 0
    } else {
        Write-CisResult -Status "FAIL" -Detail "noncompliant" -Actual $actual
        exit 1
    }
}

function Check-NetAccountsComparison {
    param([string]$Key, [string]$CompareOp, [int]$Expected)
    $out = cmd.exe /c "net accounts" 2>&1
    $actual_val = $null
    $matched_pattern = ""
    $system_access_key_map = @{
        "MaxPasswordAge"    = "MaximumPasswordAge"
        "MinPasswordAge"    = "MinimumPasswordAge"
        "MinPasswordLength" = "MinimumPasswordLength"
        "LockoutThreshold"  = "LockoutBadCount"
        "LockoutDuration"   = "LockoutDuration"
        "LockoutWindow"     = "ResetLockoutCount"
    }

    $field_patterns = @{
        "MaxPasswordAge"    = @("Maximum password age.*:\s*(\d+)")
        "MinPasswordAge"    = @("Minimum password age.*:\s*(\d+)")
        "MinPasswordLength" = @("Minimum password length.*:\s*(\d+)")
        "LockoutThreshold"  = @("Lockout threshold.*:\s*(\d+)")
        "LockoutDuration"   = @("Lockout duration.*:\s*(\d+)")
        "LockoutWindow"     = @("Reset lockout counter after.*:\s*(\d+)")
    }

    if ($system_access_key_map.ContainsKey($Key)) {
        $system_access_values = Get-SeceditSystemAccessValues
        $system_access_key = $system_access_key_map[$Key]
        if ($system_access_values.ContainsKey($system_access_key)) {
            $raw_val = $system_access_values[$system_access_key]
            if ($raw_val -match "^-?\d+$") {
                $actual_val = [int]$raw_val
                $matched_pattern = "secedit:$system_access_key"
            }
        }
    }

    if ($Key -and ($Key -ne "") -and (-not $field_patterns.ContainsKey($Key))) {
        Write-CisDebug "Check-NetAccountsComparison: unknown Key=$Key, falling back to generic value_match"
    }

    if (($null -eq $actual_val) -and $Key -and $field_patterns.ContainsKey($Key)) {
        $patterns = $field_patterns[$Key]
        foreach ($line in $out) {
            $t = $line.Trim()
            foreach ($pat in $patterns) {
                if ($t -match $pat) {
                    $actual_val = [int]$matches[1]
                    $matched_pattern = $pat
                    break
                }
            }
            if ($null -ne $actual_val) { break }
        }
    }
    elseif ($null -eq $actual_val) {
        foreach ($line in $out) {
            $t = $line.Trim()
            foreach ($key_name in $field_patterns.Keys) {
                if ($Key -eq $key_name) {
                    foreach ($pat in $field_patterns[$key_name]) {
                        if ($t -match $pat) {
                            $actual_val = [int]$matches[1]
                            $matched_pattern = $pat
                            break
                        }
                    }
                    if ($null -ne $actual_val) { break }
                }
            }
            if ($null -ne $actual_val) { break }
        }
    }

    Write-CisDebug "Check-NetAccountsComparison Key=$Key CompareOp=$CompareOp Expected=$Expected Actual=$actual_val MatchedPattern=$matched_pattern"

    if ($null -eq $actual_val) {
        Write-CisDebug "Check-NetAccountsComparison: actual_val is null, dumping net accounts output: $($out -join ' | ')"
        Write-CisResult -Status "FAIL" -Detail "value_not_found" -Actual ""
        exit 1
    }

    $ok = $false
    switch ($CompareOp) {
        "ge" { $ok = $actual_val -ge $Expected; if ($Expected -gt 0 -and $actual_val -eq 0) { $ok = $false; Write-CisDebug "Check-NetAccountsComparison: zero-exclusion triggered for ge" } }
        "le" { $ok = $actual_val -le $Expected; if ($Expected -gt 0 -and $actual_val -eq 0) { $ok = $false; Write-CisDebug "Check-NetAccountsComparison: zero-exclusion triggered for le" } }
        "gt" { $ok = $actual_val -gt $Expected }
        "lt" { $ok = $actual_val -lt $Expected }
        default { $ok = $actual_val -eq $Expected }
    }

    Write-CisDebug "Check-NetAccountsComparison result: ok=$ok actual=$actual_val expected=$Expected compare_op=$CompareOp"

    if ($ok) {
        Write-CisResult -Status "PASS" -Detail "compliant" -Actual $actual_val
        exit 0
    } else {
        Write-CisResult -Status "FAIL" -Detail "noncompliant" -Actual $actual_val
        exit 1
    }
}

function Check-NotApplicable {
    Write-CisResult -Status "UNSUPPORTED" -Detail "dc_only_or_ms_only_or_manual"
    exit 0
}

function Check-CommandExists {
    param([string]$Command, [string]$Args, [string]$ExpectedOutput)
    $result = & $Command @($Args -split ' ') 2>&1 | Out-String
    if ($result -match $ExpectedOutput) {
        Write-CisResult -Status "PASS" -Detail "compliant" -Actual ($result.Trim().Substring(0, [Math]::Min(200, $result.Length)))
        exit 0
    } else {
        Write-CisResult -Status "FAIL" -Detail "noncompliant" -Actual ($result.Trim().Substring(0, [Math]::Min(200, $result.Length)))
        exit 1
    }
}

function Check-GpoSetting {
    param([string]$RegistryPath, [string]$ValueName, [int]$Expected)
    if (-not (Test-TextValue $RegistryPath) -or -not (Test-TextValue $ValueName)) {
        Write-CisResult -Status "UNSUPPORTED" -Detail "mapping_missing_gpo_registry_path_or_name" -Actual ""
        exit 0
    }
    try {
        Check-RegistryValue -Path $RegistryPath -Name $ValueName -Expected $Expected -CompareOp "eq"
    } catch {
        Write-CisResult -Status "FAIL" -Detail "noncompliant" -Actual "registry_read_error"
        exit 1
    }
}

try {
    $mapping = Get-CheckMapping -Code $Code
    $action = $mapping.action

    switch ($action) {
        "net_accounts" {
            if ($mapping.PSObject.Properties.Name -contains "args") {
                $key_map = @{
                    "/MAXPWAGE" = "MaxPasswordAge"
                    "/MINPWAGE" = "MinPasswordAge"
                    "/MINPWLEN" = "MinPasswordLength"
                    "/LOCKOUTDURATION" = "LockoutDuration"
                    "/LOCKOUTTHRESHOLD" = "LockoutThreshold"
                    "/LOCKOUTWINDOW" = "LockoutWindow"
                }
                $expected = @{}
                foreach ($arg in $mapping.args) {
                    if ($arg -match "^/([^:]+):(.+)$") {
                        $net_key = "/$($matches[1])"
                        $local = $key_map[$net_key]
                        if ($local) { $expected[$local] = $matches[2] }
                    }
                }
                Check-NetAccounts -Expected $expected
            }
        }
        "net_accounts_compare" {
            Check-NetAccountsComparison -Key $mapping.key -CompareOp $mapping.compare_op -Expected $mapping.expected
        }
        "secedit_system_access" {
            $sa = @{}
            if ($mapping.PSObject.Properties.Name -contains "system_access") {
                $props = $mapping.system_access.PSObject.Properties
                foreach ($p in $props) { $sa[$p.Name] = [string]$p.Value }
            }
            Check-SeceditSystemAccess -Expected $sa
        }
        "secedit_privilege_rights" {
            Check-SeceditPrivilegeRights -PrivilegeName $mapping.privilege_name -ExpectedSIDList $mapping.expected_sids
        }
        "reg" {
            Check-RegistryValue -Path $mapping.path -Name $mapping.name -Expected $mapping.expected -CompareOp $mapping.compare_op
        }
        "reg_exists" {
            Check-RegistryExists -Path $mapping.path
        }
        "auditpol" {
            Check-AuditPol -Subcategory $mapping.subcategory -Success $mapping.success -Failure $mapping.failure
        }
        "service" {
            Check-Service -ServiceName $mapping.service_name -ExpectedState $mapping.expected_state
        }
        "service_startmode" {
            Check-ServiceStartMode -ServiceName $mapping.service_name -ExpectedMode $mapping.expected_mode
        }
        "firewall_profile" {
            Check-FirewallProfile -Profile $mapping.profile -Setting $mapping.setting -Expected $mapping.expected
        }
        "firewall_rule" {
            Check-FirewallRule -DisplayName $mapping.display_name -ExpectedEnabled $mapping.expected_enabled
        }
        "cmd_check" {
            Check-CommandExists -Command $mapping.command -Args $mapping.args -ExpectedOutput $mapping.expected_output
        }
        "gpo_setting" {
            Check-GpoSetting -RegistryPath $mapping.path -ValueName $mapping.name -Expected $mapping.expected
        }
        "not_applicable" {
            Check-NotApplicable
        }
        default {
            Write-CisResult -Status "ERROR" -Detail "unknown_action: $action"
            exit 1
        }
    }
} catch {
    Write-CisResult -Status "ERROR" -Detail $_.Exception.Message
    exit 1
}
