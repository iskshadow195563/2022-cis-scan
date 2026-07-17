param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "18.10.93.4.3"
exit $LASTEXITCODE
