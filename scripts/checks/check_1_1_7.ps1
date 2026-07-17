param()
$framework = Join-Path $PSScriptRoot "..\cis_check_framework.ps1"
& $framework -Code "1.1.7"
exit $LASTEXITCODE
