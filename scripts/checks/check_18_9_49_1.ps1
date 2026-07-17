param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "18.9.49.1"
exit $LASTEXITCODE
