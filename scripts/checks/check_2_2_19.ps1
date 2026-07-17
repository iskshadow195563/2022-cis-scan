param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "2.2.19"
exit $LASTEXITCODE
