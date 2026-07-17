param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "18.9.47.11.1"
exit $LASTEXITCODE
