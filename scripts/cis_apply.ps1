param(
  [string[]]$Items,
  [switch]$SelectAll,
  [string[]]$Category,
  [string]$JsonPath = "$(Split-Path $PSScriptRoot -Parent)\data\cis_items.json",
  [string]$MappingPath = "$(Split-Path $PSScriptRoot -Parent)\data\cis_mapping.json",
  [string]$ReportDir = "$(Split-Path $PSScriptRoot -Parent)\results",
  [switch]$Undo,
  [switch]$SaveBaseline,
  [switch]$RestoreBaseline,
  [string]$BaselineDir = "$(Split-Path $PSScriptRoot -Parent)\results\baseline"
)
$script:TracePath = $null

function Set-TracePath {
  param([string]$Path)
  $script:TracePath = $Path
  if (-not $Path) { return }
  $parent = Split-Path -Parent $Path
  if ($parent) { New-Item -ItemType Directory -Force -Path $parent | Out-Null }
  if (-not (Test-Path $Path)) { New-Item -ItemType File -Force -Path $Path | Out-Null }
}

function Write-Trace {
  param([string]$Message)
  $line = "{0} {1}" -f (Get-Date -Format "yyyy-MM-ddTHH:mm:ss"), $Message
  Write-Host $line
  if ($script:TracePath) {
    Add-Content -Path $script:TracePath -Value $line -Encoding UTF8
  }
}

function Require-Admin {
  $id = [System.Security.Principal.WindowsIdentity]::GetCurrent()
  $p = New-Object System.Security.Principal.WindowsPrincipal($id)
  if (-not $p.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) { Write-Error "Administrator required"; exit 1 }
}
function Ensure-EventSource {
  $src = "CISApply"
  if (-not [System.Diagnostics.EventLog]::SourceExists($src)) { New-EventLog -LogName Application -Source $src }
  $src
}
function Write-Log {
  param([string]$Source,[string]$Message,[int]$EventId=1000,[string]$EntryType="Information")
  Write-EventLog -LogName Application -Source $Source -EventId $EventId -EntryType $EntryType -Message $Message
}
function Backup-Policies {
  param([string]$Dir)
  New-Item -ItemType Directory -Force -Path $Dir | Out-Null
  $inf = Join-Path $Dir "secpol_backup.inf"
  secedit /export /cfg $inf | Out-Null
  $reg = Join-Path $Dir "registry_backup.reg"
  reg.exe export HKLM $reg /y | Out-Null
  @{ SeceditInf=$inf; RegBackup=$reg }
}
function Restore-Policies {
  param([hashtable]$Backup)
  if (Test-Path $Backup.SeceditInf) { secedit /configure /db secedit.sdb /cfg $Backup.SeceditInf /quiet | Out-Null }
  if (Test-Path $Backup.RegBackup) { reg.exe import $Backup.RegBackup | Out-Null }
}
function Export-SystemAccess {
  param([string]$path)
  secedit /export /cfg $path | Out-Null
  $values = @{}
  if (Test-Path $path) {
    $lines = Get-Content -Path $path
    $inSection = $false
    foreach ($l in $lines) {
      $t = $l.Trim()
      if ($t -eq "[System Access]") { $inSection = $true; continue }
      if ($t.StartsWith("[")) { $inSection = $false }
      if (-not $inSection -or -not $t) { continue }
      if ($t -match "^(\\w+)\\s*=\\s*(.+)$") {
        $k = $matches[1]
        $v = $matches[2].Trim()
        $values[$k] = $v
      }
    }
  }
  $values
}
function Get-NetAccountsArgs {
  $out = cmd.exe /c "net accounts"
  $args = @()
  foreach ($line in $out) {
    $t = $line.Trim()
    if ($t -match "Maximum password age.*:\\s*(\\d+)") { $args += "/MAXPWAGE:$($matches[1])" }
    elseif ($t -match "Minimum password age.*:\\s*(\\d+)") { $args += "/MINPWAGE:$($matches[1])" }
    elseif ($t -match "Minimum password length.*:\\s*(\\d+)") { $args += "/MINPWLEN:$($matches[1])" }
    elseif ($t -match "Lockout threshold.*:\\s*(\\d+)") { $args += "/LOCKOUTTHRESHOLD:$($matches[1])" }
    elseif ($t -match "Lockout duration.*:\\s*(\\d+)") { $args += "/LOCKOUTDURATION:$($matches[1])" }
    elseif ($t -match "Reset lockout counter after.*:\\s*(\\d+)") { $args += "/LOCKOUTWINDOW:$($matches[1])" }
  }
  $args | Sort-Object -Unique
}
function Create-RestorePoint {
  try { Checkpoint-Computer -Description "CISApply" -RestorePointType "MODIFY_SETTINGS" | Out-Null } catch {}
}
function Load-Json { param([string]$path) Get-Content -Raw -Path $path | ConvertFrom-Json }
function Save-CSV {
  param([object[]]$Rows,[string]$Path)
  $Rows | Export-Csv -Path $Path -NoTypeInformation -Encoding UTF8
}
function Save-HTML {
  param([object[]]$Rows,[string]$Path)
  $builder = New-Object System.Text.StringBuilder
  [void]$builder.Append("<html><head><meta charset='utf-8'><title>CIS Apply Report</title></head><body><table border='1'><tr><th>Code</th><th>Name</th><th>Status</th><th>Before</th><th>After</th><th>Error</th></tr>")
  foreach ($r in $Rows) {
    [void]$builder.Append("<tr><td>$($r.Code)</td><td>$([System.Web.HttpUtility]::HtmlEncode($r.Name))</td><td>$($r.Status)</td><td>$([System.Web.HttpUtility]::HtmlEncode($r.Before))</td><td>$([System.Web.HttpUtility]::HtmlEncode($r.After))</td><td>$([System.Web.HttpUtility]::HtmlEncode($r.Error))</td></tr>")
  }
  [void]$builder.Append("</table></body></html>")
  [IO.File]::WriteAllText($Path, $builder.ToString(), [Text.UTF8Encoding]::new($false))
}

function Get-ObjectKeys {
  param([object]$Object)
  if ($null -eq $Object) { return @() }
  if ($Object -is [hashtable]) { return @($Object.Keys) }
  return @($Object.PSObject.Properties | ForEach-Object { $_.Name })
}

function Get-ObjectValue {
  param([object]$Object,[string]$Name)
  if ($null -eq $Object) { return $null }
  if ($Object -is [hashtable]) { return $Object[$Name] }
  $prop = $Object.PSObject.Properties[$Name]
  if ($prop) { return $prop.Value }
  return $null
}

function ConvertTo-MappingHashtable {
  param([object]$Object)
  $table = @{}
  if ($null -eq $Object) { return $table }
  if ($Object -is [hashtable]) { return $Object }
  foreach ($prop in $Object.PSObject.Properties) {
    $table[$prop.Name] = $prop.Value
  }
  $table
}

function Convert-ValueLikeTemplate {
  param([object]$Value,[object]$Template)
  if ($Template -is [int] -or $Template -is [long]) {
    $text = "$Value"
    $parsed = 0
    if ([int]::TryParse($text, [ref]$parsed)) { return $parsed }
  }
  return $Value
}

function Get-NetArgLookup {
  param([string[]]$NetArgsInput)
  $lookup = @{}
  foreach ($arg in @($NetArgsInput)) {
    if (-not $arg) { continue }
    if ($arg -match "^/([^:]+):(.*)$") {
      $lookup[$matches[1].ToUpperInvariant()] = $matches[2]
    }
  }
  $lookup
}

function Test-TextValue {
  param([string]$Value)
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
    if ($p.StartsWith($prefixSlash, [StringComparison]::OrdinalIgnoreCase)) { return $p }
    if ($p.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase)) {
      $suffix = $p.Substring($prefix.Length).TrimStart([char]'\')
      return "$prefixSlash$suffix"
    }
  }
  return $p
}

function Get-NetAccountsCompareArgName {
  param([string]$Key)
  $map = @{
    "MaxPasswordAge"    = "MAXPWAGE"
    "MinPasswordAge"    = "MINPWAGE"
    "MinPasswordLength" = "MINPWLEN"
    "LockoutDuration"   = "LOCKOUTDURATION"
    "LockoutThreshold"  = "LOCKOUTTHRESHOLD"
    "LockoutWindow"     = "LOCKOUTWINDOW"
  }
  if ($map.ContainsKey($Key)) { return $map[$Key] }
  return ""
}

function Get-NetAccountsCompareArg {
  param([string]$Key,[object]$Expected)
  $argName = Get-NetAccountsCompareArgName -Key $Key
  if (-not $argName -or $null -eq $Expected -or [string]::IsNullOrWhiteSpace([string]$Expected)) {
    return ""
  }
  return "/{0}:{1}" -f $argName, $Expected
}

function Get-RegistryValueText {
  param([string]$Path,[string]$Name)
  try {
    $regPath = Normalize-RegistryPath -Path $Path
    if (-not (Test-Path $regPath)) { return "<missing-path>" }
    $item = Get-ItemProperty -Path $regPath -Name $Name -ErrorAction SilentlyContinue
    if (-not $item -or $null -eq $item.$Name) { return "<missing>" }
    return [string]$item.$Name
  } catch {
    return "<read-error: $($_.Exception.Message)>"
  }
}

function Set-RegistryExpectedValue {
  param([string]$Path,[string]$Name,[object]$Expected)
  $regPath = Normalize-RegistryPath -Path $Path
  if (-not (Test-TextValue $regPath) -or -not (Test-TextValue $Name)) {
    throw "mapping_incomplete_registry_path_or_name"
  }
  New-Item -Path $regPath -Force | Out-Null
  $propertyType = "String"
  $value = $Expected
  $intValue = 0
  if ($Expected -is [int] -or $Expected -is [long] -or [int]::TryParse([string]$Expected, [ref]$intValue)) {
    $propertyType = "DWord"
    $value = if ($Expected -is [int] -or $Expected -is [long]) { [int]$Expected } else { $intValue }
  }
  $existing = Get-ItemProperty -Path $regPath -Name $Name -ErrorAction SilentlyContinue
  if ($existing -and $null -ne $existing.$Name) {
    Set-ItemProperty -Path $regPath -Name $Name -Value $value -ErrorAction Stop
  } else {
    New-ItemProperty -Path $regPath -Name $Name -Value $value -PropertyType $propertyType -Force -ErrorAction Stop | Out-Null
  }
}

function Convert-FirewallExpectedValue {
  param([object]$Expected)
  $text = [string]$Expected
  if ($text -ieq "true") { return $true }
  if ($text -ieq "false") { return $false }
  $intValue = 0
  if ([int]::TryParse($text, [ref]$intValue)) { return $intValue }
  return $Expected
}

function New-ResultRow {
  param(
    [string]$Code,
    [string]$Name,
    [string]$Status,
    [string]$Before = "",
    [string]$After = "",
    [string]$Error = ""
  )
  [pscustomobject]@{
    Code = $Code
    Name = $Name
    Status = $Status
    Before = $Before
    After = $After
    Error = $Error
  }
}

function Build-CustomMapping {
  param([hashtable]$BaseMap,[hashtable]$sa,[string[]]$netArgs)
  $map = [ordered]@{}
  if ($null -eq $sa) { $sa = @{} }
  $netArgLookup = Get-NetArgLookup -NetArgsInput $netArgs
  foreach ($code in $BaseMap.Keys) {
    $source = $BaseMap[$code]
    $entry = ConvertTo-MappingHashtable -Object (ConvertFrom-Json -InputObject ($source | ConvertTo-Json -Depth 8))
    $action = Get-ObjectValue -Object $entry -Name "action"
    if ($action -eq "secedit_system_access") {
      $sourceSystemAccess = ConvertTo-MappingHashtable -Object (Get-ObjectValue -Object $source -Name "system_access")
      $customSystemAccess = [ordered]@{}
      foreach ($key in $sourceSystemAccess.Keys) {
        $baseValue = $sourceSystemAccess[$key]
        if ($sa.ContainsKey($key)) {
          $customSystemAccess[$key] = Convert-ValueLikeTemplate -Value $sa[$key] -Template $baseValue
        } else {
          $customSystemAccess[$key] = $baseValue
        }
      }
      $entry["system_access"] = $customSystemAccess
    } elseif ($action -eq "net_accounts") {
      $customArgs = @()
      foreach ($arg in @(Get-ObjectValue -Object $source -Name "args")) {
        if ($arg -match "^/([^:]+):") {
          $argName = $matches[1].ToUpperInvariant()
          if ($netArgLookup.ContainsKey($argName)) {
            $customArgs += "/{0}:{1}" -f $argName, $netArgLookup[$argName]
            continue
          }
        }
        $customArgs += $arg
      }
      $entry["args"] = $customArgs
    } elseif ($action -eq "net_accounts_compare") {
      $key = [string](Get-ObjectValue -Object $source -Name "key")
      $argName = Get-NetAccountsCompareArgName -Key $key
      if ($argName -and $netArgLookup.ContainsKey($argName)) {
        $entry["expected"] = $netArgLookup[$argName]
      }
    }
    $map[$code] = $entry
  }
  $map
}

function Save-CustomMapping {
  param([hashtable]$BaseMap,[hashtable]$sa,[string[]]$netArgs,[string]$path)
  $map = Build-CustomMapping -BaseMap $BaseMap -sa $sa -netArgs $netArgs
  $json = $map | ConvertTo-Json -Depth 8
  [IO.File]::WriteAllText($path, $json, [Text.UTF8Encoding]::new($false))
  $map
}

function Load-MappingTable {
  param([string]$MappingPath)
  $mappingDir = Split-Path -Parent $MappingPath
  $mappingLeaf = Split-Path -Leaf $MappingPath
  $defaultBasePath = Join-Path $mappingDir "cis_mapping.json"
  $defaultCustomPath = Join-Path $mappingDir "cis_mapping.custom.json"
  if ($mappingLeaf -ieq "cis_mapping.custom.json") {
    $basePath = $defaultBasePath
    $customPath = $MappingPath
  } else {
    $basePath = $MappingPath
    $customPath = if (Test-Path $defaultCustomPath) { $defaultCustomPath } else { $null }
  }

  $merged = @{}
  if (Test-Path $basePath) {
    foreach ($prop in (Load-Json -path $basePath).PSObject.Properties) {
      $merged[$prop.Name] = $prop.Value
    }
  }
  if ($customPath -and (Test-Path $customPath)) {
    foreach ($prop in (Load-Json -path $customPath).PSObject.Properties) {
      if ($prop.Name -like "Baseline:*") {
        Write-Trace "Ignoring legacy custom mapping key '$($prop.Name)'"
        continue
      }
      $merged[$prop.Name] = $prop.Value
    }
  }
  Write-Trace "Loaded mapping entries: basePath='$basePath' customPath='$customPath' count=$($merged.Count)"
  $merged
}

function Build-Selection {
  param([object[]]$items,[string[]]$codes,[string[]]$cats,[hashtable]$map,[switch]$all)
  if ($all) {
    $mapped = @($items | Where-Object {
      $code = Get-ObjectValue -Object $_ -Name "code"
      $code -and ($null -ne (Get-ObjectValue -Object $map -Name $code))
    })
    Write-Trace "SelectAll requested; limiting selection to mapped items count=$($mapped.Count)"
    return $mapped
  }
  $sel = @()
  foreach ($i in $items) {
    $code = Get-ObjectValue -Object $i -Name "code"
    $category = Get-ObjectValue -Object $i -Name "category"
    $okCode = $false
    $okCat = $false
    if ($codes -and ($codes -contains $code)) { $okCode = $true }
    if ($cats -and ($cats | Where-Object { $category -like "*$_*" })) { $okCat = $true }
    if ($codes -and -not $cats) { if ($okCode) { $sel += $i } }
    elseif ($cats -and -not $codes) { if ($okCat) { $sel += $i } }
    elseif ($codes -and $cats) { if ($okCode -and $okCat) { $sel += $i } }
  }
  $sel
}
function Apply-Items {
  param([object[]]$items,[hashtable]$map,[string]$reportDir)
  $src = Ensure-EventSource
  New-Item -ItemType Directory -Force -Path $reportDir | Out-Null
  Set-TracePath -Path (Join-Path $reportDir "cis_apply.log")
  Write-Trace "Applying items to reportDir='$reportDir' requestedCount=$($items.Count) mappingCount=$($map.Count)"
  $backup = Backup-Policies -Dir (Join-Path $reportDir "backup")
  Create-RestorePoint
  $rows = @()
  $sa = @{}
  $netArgs = @()
  $systemAccessRows = @()
  $netAccountRows = @()
  $privilegeRows = @()
  $privilegeRights = @{}
  $currentSa = Export-SystemAccess -path (Join-Path $reportDir "current_system_access.inf")
  $currentNetArgs = Get-NetAccountsArgs
  $currentNetLookup = Get-NetArgLookup -NetArgsInput $currentNetArgs
  foreach ($i in $items) {
    $code = Get-ObjectValue -Object $i -Name "code"
    $name = Get-ObjectValue -Object $i -Name "name"
    $m = Get-ObjectValue -Object $map -Name $code
    $action = [string](Get-ObjectValue -Object $m -Name "action")
    if (-not $m) {
      Write-Trace "Skipping code=$code reason=unmapped"
      $rows += New-ResultRow -Code $code -Name $name -Status "Skipped" -Error "Unsupported or unmapped item"
      continue
    }
    if ($action -eq "secedit_system_access") {
      $before = @()
      $after = @()
      foreach ($k in Get-ObjectKeys -Object $m.system_access) {
        $desiredValue = Get-ObjectValue -Object $m.system_access -Name $k
        $sa[$k] = $desiredValue
        $beforeValue = if ($currentSa.ContainsKey($k)) { $currentSa[$k] } else { "<missing>" }
        $before += "{0}={1}" -f $k, $beforeValue
        $after += "{0}={1}" -f $k, $desiredValue
      }
      $systemAccessRows += [pscustomobject]@{ Code=$code; Name=$name; Before=($before -join "; "); After=($after -join "; ") }
      Write-Trace "Queued code=$code action=secedit_system_access"
    } elseif ($action -eq "net_accounts") {
      $before = @()
      $after = @()
      foreach ($a in @(Get-ObjectValue -Object $m -Name "args")) {
        if ($netArgs -notcontains $a) { $netArgs += $a }
        if ($a -match "^/([^:]+):(.*)$") {
          $argName = $matches[1].ToUpperInvariant()
          $beforeValue = if ($currentNetLookup.ContainsKey($argName)) { $currentNetLookup[$argName] } else { "<missing>" }
          $before += "{0}={1}" -f $argName, $beforeValue
          $after += "{0}={1}" -f $argName, $matches[2]
        } else {
          $before += $a
          $after += $a
        }
      }
      $netAccountRows += [pscustomobject]@{ Code=$code; Name=$name; Before=($before -join "; "); After=($after -join "; ") }
      Write-Trace "Queued code=$code action=net_accounts"
    } elseif ($action -eq "net_accounts_compare") {
      $key = [string](Get-ObjectValue -Object $m -Name "key")
      $expected = Get-ObjectValue -Object $m -Name "expected"
      $arg = Get-NetAccountsCompareArg -Key $key -Expected $expected
      $argName = Get-NetAccountsCompareArgName -Key $key
      if (-not $arg) {
        Write-Trace "Skipping code=$code reason=mapping-incomplete action=net_accounts_compare key='$key'"
        $rows += New-ResultRow -Code $code -Name $name -Status "Skipped" -Error "Mapping incomplete for net_accounts_compare"
        continue
      }
      if ($netArgs -notcontains $arg) { $netArgs += $arg }
      $beforeValue = if ($currentNetLookup.ContainsKey($argName)) { $currentNetLookup[$argName] } else { "<missing>" }
      $netAccountRows += [pscustomobject]@{
        Code = $code
        Name = $name
        Before = "{0}={1}" -f $key, $beforeValue
        After = "{0}={1}" -f $key, $expected
      }
      Write-Trace "Queued code=$code action=net_accounts_compare arg='$arg'"
    } elseif ($action -eq "secedit_privilege_rights") {
      $privilegeName = [string](Get-ObjectValue -Object $m -Name "privilege_name")
      $expectedSidList = Get-ObjectValue -Object $m -Name "expected_sids"
      if (-not (Test-TextValue $privilegeName) -or $null -eq $expectedSidList -or [string]::IsNullOrWhiteSpace([string]$expectedSidList)) {
        Write-Trace "Skipping code=$code reason=mapping-incomplete action=secedit_privilege_rights"
        $rows += New-ResultRow -Code $code -Name $name -Status "Skipped" -Error "Mapping incomplete: missing privilege_name or expected_sids"
        continue
      }
      $expectedText = if ($expectedSidList -is [array]) { ($expectedSidList -join ",") } else { [string]$expectedSidList }
      $privilegeRights[$privilegeName] = $expectedText
      $privilegeRows += [pscustomobject]@{
        Code = $code
        Name = $name
        Before = ""
        After = "{0}={1}" -f $privilegeName, $expectedText
      }
      Write-Trace "Queued code=$code action=secedit_privilege_rights privilege='$privilegeName'"
    } elseif ($action -eq "gpo_setting") {
      $path = [string](Get-ObjectValue -Object $m -Name "path")
      $valueName = [string](Get-ObjectValue -Object $m -Name "name")
      $expected = Get-ObjectValue -Object $m -Name "expected"
      if (-not (Test-TextValue $path) -or -not (Test-TextValue $valueName)) {
        Write-Trace "Skipping code=$code reason=mapping-incomplete action=gpo_setting"
        $rows += New-ResultRow -Code $code -Name $name -Status "Skipped" -Error "Mapping incomplete: missing registry path or value name"
        continue
      }
      $before = Get-RegistryValueText -Path $path -Name $valueName
      $after = "{0}\{1}={2}" -f (Normalize-RegistryPath -Path $path), $valueName, $expected
      try {
        Set-RegistryExpectedValue -Path $path -Name $valueName -Expected $expected
        Write-Log -Source $src -Message "Applied $code $name" -EventId 1001 -EntryType "Information"
        Write-Trace "Applied code=$code action=gpo_setting path='$path' name='$valueName'"
        $rows += New-ResultRow -Code $code -Name $name -Status "Pass" -Before $before -After $after
      } catch {
        $err = $_.Exception.Message
        Write-Log -Source $src -Message "Failed $code $err" -EventId 1002 -EntryType "Error"
        Write-Trace "Failed code=$code action=gpo_setting error=$err"
        $rows += New-ResultRow -Code $code -Name $name -Status "Fail" -Before $before -After $after -Error $err
      }
    } elseif ($action -eq "firewall_profile") {
      $profile = [string](Get-ObjectValue -Object $m -Name "profile")
      $setting = [string](Get-ObjectValue -Object $m -Name "setting")
      $expected = Get-ObjectValue -Object $m -Name "expected"
      if (-not (Test-TextValue $profile) -or -not (Test-TextValue $setting) -or $null -eq $expected) {
        Write-Trace "Skipping code=$code reason=mapping-incomplete action=firewall_profile"
        $rows += New-ResultRow -Code $code -Name $name -Status "Skipped" -Error "Mapping incomplete: missing firewall profile, setting, or expected value"
        continue
      }
      $before = ""
      $after = "{0}.{1}={2}" -f $profile, $setting, $expected
      try {
        $fw = Get-NetFirewallProfile -Name $profile -ErrorAction Stop
        $before = [string]$fw.$setting
        $params = @{ Name = $profile }
        $params[$setting] = Convert-FirewallExpectedValue -Expected $expected
        Set-NetFirewallProfile @params -ErrorAction Stop
        Write-Log -Source $src -Message "Applied $code $name" -EventId 1001 -EntryType "Information"
        Write-Trace "Applied code=$code action=firewall_profile profile='$profile' setting='$setting'"
        $rows += New-ResultRow -Code $code -Name $name -Status "Pass" -Before $before -After $after
      } catch {
        $err = $_.Exception.Message
        Write-Log -Source $src -Message "Failed $code $err" -EventId 1002 -EntryType "Error"
        Write-Trace "Failed code=$code action=firewall_profile error=$err"
        $rows += New-ResultRow -Code $code -Name $name -Status "Fail" -Before $before -After $after -Error $err
      }
    } elseif ($action -eq "service") {
      $serviceName = [string](Get-ObjectValue -Object $m -Name "service_name")
      $expectedState = [string](Get-ObjectValue -Object $m -Name "expected_state")
      if (-not (Test-TextValue $serviceName) -or -not (Test-TextValue $expectedState)) {
        Write-Trace "Skipping code=$code reason=mapping-incomplete action=service"
        $rows += New-ResultRow -Code $code -Name $name -Status "Skipped" -Error "Mapping incomplete: missing service name or expected state"
        continue
      }
      $before = ""
      try {
        $svc = Get-Service -Name $serviceName -ErrorAction Stop
        $before = $svc.Status.ToString()
        if ($expectedState -ieq "Stopped") {
          if ($svc.Status -ne "Stopped") { Stop-Service -Name $serviceName -Force -ErrorAction Stop }
        } elseif ($expectedState -ieq "Running") {
          if ($svc.Status -ne "Running") { Start-Service -Name $serviceName -ErrorAction Stop }
        } else {
          throw "Unsupported service expected_state: $expectedState"
        }
        Write-Log -Source $src -Message "Applied $code $name" -EventId 1001 -EntryType "Information"
        Write-Trace "Applied code=$code action=service service='$serviceName' expected='$expectedState'"
        $rows += New-ResultRow -Code $code -Name $name -Status "Pass" -Before $before -After $expectedState
      } catch {
        $err = $_.Exception.Message
        Write-Log -Source $src -Message "Failed $code $err" -EventId 1002 -EntryType "Error"
        Write-Trace "Failed code=$code action=service error=$err"
        $rows += New-ResultRow -Code $code -Name $name -Status "Fail" -Before $before -After $expectedState -Error $err
      }
    } elseif ($action -eq "auditpol") {
      $before = ""
      $after = "success=$($m.success); failure=$($m.failure)"
      $err = ""
      try {
        $subcategory = [string]$m.subcategory
        if (-not (Test-TextValue $subcategory)) {
          Write-Trace "Skipping code=$code reason=mapping-incomplete action=auditpol"
          $rows += New-ResultRow -Code $code -Name $name -Status "Skipped" -Before $before -After $after -Error "Mapping incomplete: missing auditpol subcategory"
          continue
        }
        if ($subcategory -match "^Audit\s+(.+)$") { $subcategory = $matches[1] }
        $cmd = "auditpol /set /subcategory:`"$subcategory`" /success:$($m.success) /failure:$($m.failure)"
        $out = cmd.exe /c $cmd 2>&1
        if ($LASTEXITCODE -ne 0) { throw (($out | Out-String).Trim()) }
        Write-Log -Source $src -Message "Applied $code $name" -EventId 1001 -EntryType "Information"
        Write-Trace "Applied code=$code action=auditpol"
        $rows += New-ResultRow -Code $code -Name $name -Status "Pass" -Before $before -After $after
      } catch {
        $err = $_.Exception.Message
        Write-Log -Source $src -Message "Failed $code $err" -EventId 1002 -EntryType "Error"
        Write-Trace "Failed code=$code action=auditpol error=$err"
        $rows += New-ResultRow -Code $code -Name $name -Status "Fail" -Before $before -After $after -Error $err
      }
    } else {
      Write-Trace "Skipping code=$code reason=unsupported-action action=$action"
      $rows += New-ResultRow -Code $code -Name $name -Status "Skipped" -Error "Unsupported action: $action"
    }
  }
  if ($sa.Count -gt 0 -and $systemAccessRows.Count -gt 0) {
    $inf = "[Version]`nSignature=`"`$CHICAGO`$`"`nRevision=1`n[System Access]`n"
    foreach ($k in $sa.Keys) { $inf += "$k = $($sa[$k])`n" }
    $infPath = Join-Path $reportDir "apply_system_access.inf"
    [IO.File]::WriteAllText($infPath, $inf)
    try {
      Write-Trace "Applying batch action=secedit_system_access itemCount=$($systemAccessRows.Count)"
      secedit /configure /db secedit.sdb /cfg $infPath /quiet | Out-Null
      foreach ($entry in $systemAccessRows) {
        $rows += New-ResultRow -Code $entry.Code -Name $entry.Name -Status "Pass" -Before $entry.Before -After $entry.After
      }
      Write-Log -Source $src -Message "Applied System Access" -EventId 1003 -EntryType "Information"
      Write-Trace "Applied batch action=secedit_system_access"
    } catch {
      $err = $_.Exception.Message
      Write-Log -Source $src -Message "System Access failure $_" -EventId 1004 -EntryType "Error"
      Write-Trace "Failed batch action=secedit_system_access error=$err"
      foreach ($entry in $systemAccessRows) {
        $rows += New-ResultRow -Code $entry.Code -Name $entry.Name -Status "Fail" -Before $entry.Before -After $entry.After -Error $err
      }
    }
  }
  if ($privilegeRights.Count -gt 0 -and $privilegeRows.Count -gt 0) {
    $inf = "[Version]`nSignature=`"`$CHICAGO`$`"`nRevision=1`n[Privilege Rights]`n"
    foreach ($k in $privilegeRights.Keys) { $inf += "$k = $($privilegeRights[$k])`n" }
    $infPath = Join-Path $reportDir "apply_privilege_rights.inf"
    [IO.File]::WriteAllText($infPath, $inf)
    try {
      Write-Trace "Applying batch action=secedit_privilege_rights itemCount=$($privilegeRows.Count)"
      secedit /configure /db secedit.sdb /cfg $infPath /quiet | Out-Null
      foreach ($entry in $privilegeRows) {
        $rows += New-ResultRow -Code $entry.Code -Name $entry.Name -Status "Pass" -Before $entry.Before -After $entry.After
      }
      Write-Log -Source $src -Message "Applied Privilege Rights" -EventId 1007 -EntryType "Information"
      Write-Trace "Applied batch action=secedit_privilege_rights"
    } catch {
      $err = $_.Exception.Message
      Write-Log -Source $src -Message "Privilege Rights failure $_" -EventId 1008 -EntryType "Error"
      Write-Trace "Failed batch action=secedit_privilege_rights error=$err"
      foreach ($entry in $privilegeRows) {
        $rows += New-ResultRow -Code $entry.Code -Name $entry.Name -Status "Fail" -Before $entry.Before -After $entry.After -Error $err
      }
    }
  }
  if ($netArgs.Count -gt 0 -and $netAccountRows.Count -gt 0) {
    $cmd = "net accounts " + ($netArgs -join " ")
    try {
      Write-Trace "Applying batch action=net_accounts itemCount=$($netAccountRows.Count) args='$($netArgs -join " ")'"
      $out = cmd.exe /c $cmd 2>&1
      if ($LASTEXITCODE -ne 0) { throw (($out | Out-String).Trim()) }
      Write-Log -Source $src -Message "Applied net accounts" -EventId 1005 -EntryType "Information"
      Write-Trace "Applied batch action=net_accounts"
      foreach ($entry in $netAccountRows) {
        $rows += New-ResultRow -Code $entry.Code -Name $entry.Name -Status "Pass" -Before $entry.Before -After $entry.After
      }
    } catch {
      $err = $_.Exception.Message
      Write-Log -Source $src -Message "net accounts failure $_" -EventId 1006 -EntryType "Error"
      Write-Trace "Failed batch action=net_accounts error=$err"
      foreach ($entry in $netAccountRows) {
        $rows += New-ResultRow -Code $entry.Code -Name $entry.Name -Status "Fail" -Before $entry.Before -After $entry.After -Error $err
      }
    }
  }
  $csv = Join-Path $reportDir "cis_apply.csv"
  $html = Join-Path $reportDir "cis_apply.html"
  Save-CSV -Rows $rows -Path $csv
  Save-HTML -Rows $rows -Path $html
  Write-Trace "Saved reports csv='$csv' html='$html' rows=$($rows.Count)"
  $rows
}

function Invoke-CISApplyMain {
  Require-Admin
  if ($SaveBaseline) {
    $src = Ensure-EventSource
    New-Item -ItemType Directory -Force -Path $BaselineDir | Out-Null
    Set-TracePath -Path (Join-Path $BaselineDir "baseline_save.log")
    Write-Trace "Saving baseline to '$BaselineDir'"
    $saInf = Join-Path $BaselineDir "secpol_baseline.inf"
    $reg = Join-Path $BaselineDir "registry_baseline.reg"
    secedit /export /cfg $saInf | Out-Null
    reg.exe export HKLM $reg /y | Out-Null
    $sa = Export-SystemAccess -path $saInf
    $netArgs = Get-NetAccountsArgs
    $baseMapPath = "$(Split-Path $PSScriptRoot -Parent)\data\cis_mapping.json"
    $customMapPath = "$(Split-Path $PSScriptRoot -Parent)\data\cis_mapping.custom.json"
    $baseMap = ConvertTo-MappingHashtable -Object (Load-Json -path $baseMapPath)
    $mapObj = Save-CustomMapping -BaseMap $baseMap -sa $sa -netArgs $netArgs -path $customMapPath
    Write-Trace "Saved baseline snapshot systemAccessCount=$($sa.Count) netAccountsCount=$($netArgs.Count) customMappingCount=$($mapObj.Count)"
    Write-Log -Source $src -Message "Saved baseline and custom mapping." -EventId 1100 -EntryType "Information"
    Write-Output "Saved baseline to $BaselineDir and custom mapping to $customMapPath"
    exit 0
  }
  if ($RestoreBaseline) {
    $src = Ensure-EventSource
    New-Item -ItemType Directory -Force -Path $ReportDir | Out-Null
    Set-TracePath -Path (Join-Path $ReportDir "baseline_restore.log")
    Write-Trace "Restoring baseline from '$BaselineDir'"
    $pre = Backup-Policies -Dir (Join-Path $ReportDir "restore_pre_backup")
    $saInf = Join-Path $BaselineDir "secpol_baseline.inf"
    $reg = Join-Path $BaselineDir "registry_baseline.reg"
    $err = $null
    try {
      if (Test-Path $saInf) { secedit /configure /db secedit.sdb /cfg $saInf /quiet | Out-Null }
      if (Test-Path $reg) { reg.exe import $reg | Out-Null }
      $netArgs = Get-NetAccountsArgs
      if ($netArgs.Count -gt 0) {
        $cmd = "net accounts " + ($netArgs -join " ")
        cmd.exe /c $cmd | Out-Null
      }
      Write-Log -Source $src -Message "Restored baseline." -EventId 1101 -EntryType "Information"
      Write-Trace "Restored baseline successfully"
      Write-Output "Restored baseline from $BaselineDir"
      exit 0
    } catch {
      $err = $_.Exception.Message
      Write-Log -Source $src -Message "Restore baseline failed: $err" -EventId 1102 -EntryType "Error"
      Write-Trace "Restore baseline failed error=$err"
      Restore-Policies -Backup $pre
      Write-Error "Restore failed: $err"
      exit 1
    }
  }
  if ($Undo) {
    Set-TracePath -Path (Join-Path $ReportDir "undo.log")
    Write-Trace "Undo requested reportDir='$ReportDir'"
    $backupDir = Join-Path $ReportDir "backup"
    $b = @{ SeceditInf=(Join-Path $backupDir "secpol_backup.inf"); RegBackup=(Join-Path $backupDir "registry_backup.reg") }
    Restore-Policies -Backup $b
    exit 0
  }
  $items = Load-Json -path $JsonPath
  $map = Load-MappingTable -MappingPath $MappingPath
  $sel = Build-Selection -items $items -codes $Items -cats $Category -map $map -all:$SelectAll
  $res = Apply-Items -items $sel -map $map -reportDir $ReportDir
  Write-Output $res
}

if ($MyInvocation.InvocationName -ne ".") {
  Invoke-CISApplyMain
}
