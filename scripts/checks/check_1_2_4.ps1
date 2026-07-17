param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "1.2.4"
exit $LASTEXITCODE
