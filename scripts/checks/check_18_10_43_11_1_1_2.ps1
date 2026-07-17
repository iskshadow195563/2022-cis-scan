param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "18.10.43.11.1.1.2"
exit $LASTEXITCODE
