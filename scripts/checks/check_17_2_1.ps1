param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "17.2.1"
exit $LASTEXITCODE
