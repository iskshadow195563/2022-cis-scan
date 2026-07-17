param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "18.10.57.3.2.1"
exit $LASTEXITCODE
