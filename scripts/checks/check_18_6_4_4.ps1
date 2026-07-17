param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "18.6.4.4"
exit $LASTEXITCODE
