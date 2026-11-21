# Funciones comunes de los scripts de RastroJuliaca (se cargan con ". .\_entorno.ps1").
# Detectan un intérprete Python 3.12 que realmente se pueda ejecutar en este equipo. Algunos equipos
# (Control inteligente de aplicaciones, antivirus o políticas de la organización) bloquean ciertos
# ejecutables, por lo que se prueba cada candidato en lugar de suponer una ruta fija.

$script:RJRoot = Split-Path -Parent $PSScriptRoot
$script:RJBackend = Join-Path $script:RJRoot "backend"
$script:RJFrontend = Join-Path $script:RJRoot "frontend"
# Nombres de entorno virtual que se buscan dentro de backend/, en orden de preferencia
$script:RJVenvNames = @(".venv", ".venv_alt", ".venv-rj")

function Test-RJPython {
    param([string]$Path, [switch]$RequireDeps)
    if (-not $Path -or -not (Test-Path $Path)) { return $false }
    $code = "import sys; assert sys.version_info[:2] == (3, 12)"
    if ($RequireDeps) { $code += "; import fastapi, uvicorn, sqlalchemy, alembic" }
    try {
        & $Path -c $code 2>$null | Out-Null
        return ($LASTEXITCODE -eq 0)
    } catch {
        # Ejecutable bloqueado por el sistema (p. ej. "Acceso denegado")
        return $false
    }
}

function Get-RJVenvCandidates {
    $list = @()
    if ($env:RJ_VENV) {
        $v = if ([System.IO.Path]::IsPathRooted($env:RJ_VENV)) { $env:RJ_VENV } else { Join-Path $script:RJBackend $env:RJ_VENV }
        $list += $v
    }
    foreach ($n in $script:RJVenvNames) { $list += (Join-Path $script:RJBackend $n) }
    return $list
}

function Find-RJVenvPython {
    <# Devuelve la ruta al python.exe del primer entorno virtual que funcione, o $null. #>
    param([switch]$RequireDeps)
    foreach ($v in Get-RJVenvCandidates) {
        $py = Join-Path $v "Scripts\python.exe"
        if (Test-RJPython -Path $py -RequireDeps:$RequireDeps) { return $py }
    }
    return $null
}

function Find-RJBasePython {
    <# Busca un Python 3.12 base (no virtual) ejecutable para crear el entorno. #>
    $candidates = @()
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try { $candidates += (& py -3.12 -c "import sys; print(sys.executable)" 2>$null) } catch { }
    }
    if (Get-Command uv -ErrorAction SilentlyContinue) {
        try { $candidates += (& uv python find 3.12 2>$null) } catch { }
    }
    foreach ($name in @("python3.12", "python")) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        if ($cmd) { $candidates += $cmd.Source }
    }
    foreach ($c in $candidates) {
        if ($c) {
            $p = "$c".Trim()
            if (Test-RJPython -Path $p) { return $p }
        }
    }
    return $null
}

function Get-RJRequiredPython {
    $py = Find-RJVenvPython -RequireDeps
    if (-not $py) {
        throw "No se encontró un entorno Python 3.12 funcional con dependencias en backend\(.venv|.venv_alt|.venv-rj). Ejecute primero .\scripts\setup.ps1"
    }
    return $py
}
