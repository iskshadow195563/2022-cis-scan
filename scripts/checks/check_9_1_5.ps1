param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "9.1.5"
exit $LASTEXITCODE
