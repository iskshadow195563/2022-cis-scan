param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "18.10.43.6.3.1"
exit $LASTEXITCODE
