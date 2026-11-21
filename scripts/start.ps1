<#
.SYNOPSIS
  Inicia RastroJuliaca solo en la interfaz local (127.0.0.1). No expone el servidor a la red.
.PARAMETER Dev
  Modo desarrollo: backend con recarga automática + servidor Vite en http://127.0.0.1:5173
.PARAMETER Port
  Puerto del backend (por defecto 8000).
#>
param([switch]$Dev, [int]$Port = 8000)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_entorno.ps1")
$py = Get-RJRequiredPython
Write-Host "Python: $py"

Push-Location $RJBackend
try {
    if ($Dev) {
        Write-Host "Iniciando Vite en http://127.0.0.1:5173 (ventana aparte)" -ForegroundColor Cyan
        Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location '$RJFrontend'; npm run dev"
        & $py -m uvicorn app.main:app --host 127.0.0.1 --port $Port --reload
    } else {
        if (-not (Test-Path (Join-Path $RJFrontend "dist\index.html"))) { throw "Frontend no compilado: ejecute .\scripts\setup.ps1" }
        Write-Host "RastroJuliaca disponible en http://127.0.0.1:$Port  (Ctrl+C para detener)" -ForegroundColor Green
        & $py -m uvicorn app.main:app --host 127.0.0.1 --port $Port
    }
} finally { Pop-Location }
