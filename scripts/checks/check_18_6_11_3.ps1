param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "18.6.11.3"
exit $LASTEXITCODE
