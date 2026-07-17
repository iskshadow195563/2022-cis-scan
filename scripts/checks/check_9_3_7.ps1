param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "9.3.7"
exit $LASTEXITCODE
