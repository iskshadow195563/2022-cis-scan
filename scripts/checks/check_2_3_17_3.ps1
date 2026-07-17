param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "2.3.17.3"
exit $LASTEXITCODE
