param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "17.8.1"
exit $LASTEXITCODE
