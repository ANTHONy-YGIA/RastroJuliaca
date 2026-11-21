<#
.SYNOPSIS
  Ejecuta Python con el entorno del proyecto detectado automáticamente.
.EXAMPLE
  .\scripts\py.ps1 experiment\generar_conjuntos.py
#>
$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "_entorno.ps1")
$py = Get-RJRequiredPython
& $py @args
exit $LASTEXITCODE
