param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "19.6.6.1.1"
exit $LASTEXITCODE
