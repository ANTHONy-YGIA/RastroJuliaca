<#
.SYNOPSIS
  Instala RastroJuliaca en Windows 11 (sin Docker).
.DESCRIPTION
  1. Verifica herramientas (Python 3.12, Node.js, FFmpeg, antivirus).
  2. Crea .env con un secreto aleatorio si no existe (nunca sobrescribe uno existente).
  3. Reutiliza un entorno virtual que funcione o crea uno nuevo con "python -m venv" (no borra entornos existentes).
  4. Instala dependencias del backend y del frontend y compila el frontend.
  5. Aplica migraciones y carga datos ficticios SOLO si la base de datos está vacía.
.PARAMETER VenvDir
  Nombre o ruta del entorno virtual a crear/usar (por defecto: el primero que funcione de .venv, .venv_alt, .venv-rj).
.PARAMETER Reset
  Elimina la BD y archivos locales de data/ y vuelve a sembrar los datos ficticios. Pide confirmación.
.PARAMETER WithE2E
  Descarga además el navegador Chromium de Playwright para las pruebas de extremo a extremo.
#>
param([string]$VenvDir = "", [switch]$Reset, [switch]$WithE2E)
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_entorno.ps1")

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }
function Warn($msg) { Write-Host "AVISO: $msg" -ForegroundColor Yellow }

Step "Verificando herramientas"
if (-not (Get-Command node -ErrorAction SilentlyContinue)) { throw "Node.js 20 o superior es obligatorio: https://nodejs.org" }
Write-Host ("Node.js " + (node --version))
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) { Write-Host "FFmpeg disponible" } else { Warn "FFmpeg no encontrado: los videos quedarán bloqueados hasta poder validarlos (winget install Gyan.FFmpeg)" }
$defender = Join-Path $env:ProgramFiles "Windows Defender\MpCmdRun.exe"
if (Test-Path $defender) { Write-Host "Microsoft Defender disponible para análisis de archivos" }
elseif (Get-Command clamscan -ErrorAction SilentlyContinue) { Write-Host "ClamAV disponible" }
else { Warn "No se encontró antivirus: los archivos permanecerán bloqueados en cuarentena" }

Step "Configuración (.env)"
$envFile = Join-Path $RJRoot ".env"
if (-not (Test-Path $envFile)) {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secret = [Convert]::ToBase64String($bytes)
    (Get-Content (Join-Path $RJRoot ".env.example")) -replace '^RJ_SECRET_KEY=.*', "RJ_SECRET_KEY=$secret" | Set-Content $envFile -Encoding utf8
    Write-Host ".env creado con un secreto aleatorio"
} else { Write-Host ".env existente conservado" }

Step "Backend: entorno virtual Python 3.12"
if ($VenvDir) { $env:RJ_VENV = $VenvDir }
$py = Find-RJVenvPython
if ($py) {
    Write-Host "Se reutiliza el entorno: $py"
} else {
    $base = Find-RJBasePython
    if (-not $base) {
        throw "No se encontró Python 3.12 ejecutable. Instale Python 3.12 desde python.org (recomendado) o con 'uv python install 3.12', y vuelva a ejecutar."
    }
    # Elegir un directorio que no exista: nunca se borra un entorno previo (aunque esté dañado)
    $target = $null
    foreach ($cand in Get-RJVenvCandidates) { if (-not (Test-Path $cand)) { $target = $cand; break } }
    if (-not $target) { throw "Todos los nombres de entorno ya existen pero ninguno funciona. Indique uno nuevo con -VenvDir .venv-nuevo" }
    Write-Host "Creando entorno con '$base -m venv' en $target"
    & $base -m venv $target
    if ($LASTEXITCODE -ne 0) { throw "No se pudo crear el entorno virtual" }
    $py = Join-Path $target "Scripts\python.exe"
    if (-not (Test-RJPython -Path $py)) {
        throw "Windows impidió ejecutar $py (Control inteligente de aplicaciones, antivirus o política del equipo). Instale Python 3.12 desde python.org (instalador firmado) y ejecute de nuevo con -VenvDir .venv-python-org"
    }
}
& $py --version
& $py -m pip install --disable-pip-version-check -q -e "$RJBackend[dev]"
if ($LASTEXITCODE -ne 0) { throw "Fallo al instalar dependencias del backend" }
if (-not (Test-RJPython -Path $py -RequireDeps)) { throw "Las dependencias del backend no quedaron instaladas correctamente" }

Step "Frontend: dependencias y compilación"
Push-Location $RJFrontend
try {
    if (Test-Path "package-lock.json") { npm ci } else { npm install }
    if ($LASTEXITCODE -ne 0) { throw "Fallo npm install" }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "Fallo la compilación del frontend" }
    if ($WithE2E) { npx playwright install chromium }
} finally { Pop-Location }

Step "Base de datos: migraciones y datos ficticios"
Push-Location $RJBackend
try {
    if ($Reset) {
        $answer = Read-Host "Esto ELIMINA la base de datos y los archivos de data/ (no se puede deshacer). Escriba SI para continuar"
        if ($answer -ne "SI") { throw "Operación cancelada por el usuario" }
        & $py -m app.seed --reset
    } else {
        # Migra y siembra solo si la BD está vacía; una BD existente se conserva
        & $py -m app.seed
    }
    if ($LASTEXITCODE -ne 0) { throw "Fallo la inicialización de la base de datos" }
} finally { Pop-Location }

Write-Host "`nInstalación completa. Inicie con: .\scripts\start.ps1" -ForegroundColor Green
