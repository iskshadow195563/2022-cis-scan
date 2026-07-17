param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "2.3.11.6"
exit $LASTEXITCODE
