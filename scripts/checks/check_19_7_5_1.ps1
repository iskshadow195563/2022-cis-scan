param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "19.7.5.1"
exit $LASTEXITCODE
