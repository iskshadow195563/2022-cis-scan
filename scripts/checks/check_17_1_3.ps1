param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "17.1.3"
exit $LASTEXITCODE
