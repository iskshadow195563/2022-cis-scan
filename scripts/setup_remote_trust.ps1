#Requires -RunAsAdministrator

<#
.SYNOPSIS
    Configure WinRM TrustedHosts on the REMOTE server (WIN-EKEG740HTS6, 192.168.135.137)
    to trust the LOCAL server (TEST-DC, 192.168.135.136) for remote scanning.
.DESCRIPTION
    This script adds the local server's IP and hostname to the remote TrustedHosts list,
    enables WS-Management (WinRM) remoting, and configures firewall rules for port 5985/5986.
.NOTES
    Run this script on: WIN-EKEG740HTS6 (192.168.135.137)
    Trusting local server: TEST-DC (192.168.135.136)
#>

$ErrorActionPreference = "Stop"

# --- Configuration ---
$LocalIP        = "192.168.135.136"
$LocalHostname  = "TEST-DC"
$RemoteIP       = "192.168.135.137"
$RemoteHostname = "WIN-EKEG740HTS6"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Remote Trust Configuration" -ForegroundColor Cyan
Write-Host "  Machine : $RemoteHostname ($RemoteIP)" -ForegroundColor Cyan
Write-Host "  Trust   : $LocalHostname ($LocalIP)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# --- Step 1: Check / Enable WinRM ---
Write-Host "[1/5] Checking WinRM service..." -ForegroundColor Yellow
$winrm = Get-Service -Name "WinRM" -ErrorAction SilentlyContinue
if (-not $winrm -or $winrm.Status -ne "Running") {
    Write-Host "  WinRM is not running. Enabling..." -ForegroundColor Gray
    Enable-PSRemoting -Force -SkipNetworkProfileCheck
    Write-Host "  WinRM enabled successfully." -ForegroundColor Green
} else {
    Write-Host "  WinRM is already running." -ForegroundColor Green
}

# --- Step 2: Configure TrustedHosts ---
Write-Host ""
Write-Host "[2/5] Configuring TrustedHosts..." -ForegroundColor Yellow
$current = (Get-Item WSMan:\localhost\Client\TrustedHosts).Value
$entries = @()
if ($current) {
    $entries = $current -split "," | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
}

$newEntries = @()
if ($LocalIP -notin $entries) { $newEntries += $LocalIP }
if ($LocalHostname -notin $entries) { $newEntries += $LocalHostname }

if ($newEntries.Count -gt 0) {
    $combined = ($entries + $newEntries) -join ","
    Set-Item WSMan:\localhost\Client\TrustedHosts -Value $combined -Force
    Write-Host "  Added to TrustedHosts: $($newEntries -join ', ')" -ForegroundColor Green
} else {
    Write-Host "  TrustedHosts already contains the local entries." -ForegroundColor Green
}
Write-Host "  Current TrustedHosts: $((Get-Item WSMan:\localhost\Client\TrustedHosts).Value)" -ForegroundColor Gray

# --- Step 3: Allow Unencrypted (if needed for HTTP) ---
Write-Host ""
Write-Host "[3/5] Checking AllowUnencrypted setting..." -ForegroundColor Yellow
$allowUnencrypted = (Get-Item WSMan:\localhost\Client\AllowUnencrypted).Value
if ($allowUnencrypted -ne "true") {
    Set-Item WSMan:\localhost\Client\AllowUnencrypted -Value $true -Force
    Write-Host "  AllowUnencrypted set to True (required for HTTP transport)." -ForegroundColor Green
} else {
    Write-Host "  AllowUnencrypted is already True." -ForegroundColor Green
}

# --- Step 4: Firewall Rules for WinRM ---
Write-Host ""
Write-Host "[4/5] Configuring Windows Firewall for WinRM..." -ForegroundColor Yellow
$rules = @(
    @{Name="WinRM-HTTP"; Port=5985; Protocol="TCP"},
    @{Name="WinRM-HTTPS"; Port=5986; Protocol="TCP"}
)
foreach ($rule in $rules) {
    $existing = Get-NetFirewallRule -DisplayName $rule.Name -ErrorAction SilentlyContinue
    if (-not $existing) {
        New-NetFirewallRule -DisplayName $rule.Name -Direction Inbound -Protocol $rule.Protocol -LocalPort $rule.Port -Action Allow -Profile Any | Out-Null
        Write-Host "  Firewall rule '$($rule.Name)' (port $($rule.Port)) created." -ForegroundColor Green
    } else {
        Write-Host "  Firewall rule '$($rule.Name)' already exists." -ForegroundColor Green
    }
}

# --- Step 5: Verify Connectivity ---
Write-Host ""
Write-Host "[5/5] Verifying WinRM connectivity to $LocalIP..." -ForegroundColor Yellow
try {
    $result = Test-WSMan -ComputerName $LocalIP -ErrorAction Stop
    Write-Host "  WinRM connectivity OK." -ForegroundColor Green
    Write-Host "  Local Product: $($result.ProductVendor)" -ForegroundColor Gray
    Write-Host "  Local Version: $($result.ProductVersion)" -ForegroundColor Gray
} catch {
    Write-Host "  WARNING: Cannot verify WinRM connectivity to $LocalIP." -ForegroundColor Red
    Write-Host "  This is expected if the local server has not been configured yet." -ForegroundColor Yellow
    Write-Host "  Error: $_" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Remote trust setup complete!" -ForegroundColor Cyan
Write-Host "  Both servers should now trust each other." -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
