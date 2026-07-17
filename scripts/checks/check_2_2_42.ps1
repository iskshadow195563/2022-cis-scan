param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "2.2.42"
exit $LASTEXITCODE
