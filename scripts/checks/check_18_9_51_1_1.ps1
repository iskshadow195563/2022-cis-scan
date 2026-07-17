param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "18.9.51.1.1"
exit $LASTEXITCODE
