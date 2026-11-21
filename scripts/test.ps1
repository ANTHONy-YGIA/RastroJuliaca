<#
.SYNOPSIS
  Ejecuta las pruebas automatizadas y guarda la evidencia en docs/evidencias/.
  No modifica la base de datos principal: las pruebas usan BD y almacenamiento temporales o aislados.
.PARAMETER SkipE2E
  Omite las pruebas de extremo a extremo con Playwright.
#>
param([switch]$SkipE2E)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_entorno.ps1")
$py = Get-RJRequiredPython
# En Windows PowerShell 5.1, "Stop" convierte cualquier línea de stderr de un programa externo en error
# fatal; se usa "Continue" y se evalúa el código de salida de cada herramienta.
$ErrorActionPreference = "Continue"
$env:RJ_PYTHON = $py   # lo usa playwright.config.ts para iniciar el servidor E2E aislado
$Evid = Join-Path $RJRoot "docs\evidencias"
New-Item -ItemType Directory -Force $Evid | Out-Null
$failed = $false

Write-Host "`n==> Pruebas del backend (pytest) con $py" -ForegroundColor Cyan
Push-Location $RJBackend
try {
    & $py -c "import pytest" 2>$null
    if ($LASTEXITCODE -ne 0) { & $py -m pip install --disable-pip-version-check -q -e ".[dev]" }
    & $py -m pytest -p no:warnings -rs --junitxml="$Evid\pytest-junit.xml" 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath "$Evid\pytest-salida.txt"
    if ($LASTEXITCODE -ne 0) { $failed = $true }
    # No conservar el nombre del equipo en la evidencia
    $junit = "$Evid\pytest-junit.xml"
    if (Test-Path $junit) { (Get-Content $junit -Raw) -replace ' hostname="[^"]*"', '' | Set-Content $junit -Encoding utf8 }
} finally { Pop-Location }

Write-Host "`n==> Verificación de tipos y compilación del frontend" -ForegroundColor Cyan
Push-Location $RJFrontend
try {
    npm run build 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath "$Evid\frontend-build.txt"
    if ($LASTEXITCODE -ne 0) { $failed = $true }
    if (-not $SkipE2E) {
        Write-Host "`n==> Pruebas de extremo a extremo y móviles (Playwright)" -ForegroundColor Cyan
        npx playwright test 2>&1 | ForEach-Object { "$_" } | Tee-Object -FilePath "$Evid\playwright-salida.txt"
        if ($LASTEXITCODE -ne 0) { $failed = $true }
    }
} finally { Pop-Location }

if ($failed) { Write-Host "`nAlgunas pruebas FALLARON. Revise docs\evidencias." -ForegroundColor Red; exit 1 }
Write-Host "`nTodas las pruebas ejecutadas pasaron. Evidencia en docs\evidencias." -ForegroundColor Green
