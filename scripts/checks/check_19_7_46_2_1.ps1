param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "19.7.46.2.1"
exit $LASTEXITCODE
