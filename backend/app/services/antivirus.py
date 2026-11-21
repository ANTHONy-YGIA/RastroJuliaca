"""Integración con antivirus del sistema.

- Windows: Microsoft Defender (MpCmdRun.exe) con análisis personalizado de un archivo.
- Alternativa: ClamAV (clamdscan / clamscan) si está en el PATH.

Si no hay un motor operativo el resultado es ``unavailable`` y el archivo permanece
bloqueado en cuarentena. Nunca se simula un análisis exitoso.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from ..config import get_settings


@dataclass
class ScanResult:
    status: str  # clean | infected | error | unavailable
    engine: str
    detail: str = ""


class Scanner:
    name = "none"

    def available(self) -> bool:  # pragma: no cover - interfaz
        return False

    def scan(self, path: Path) -> ScanResult:  # pragma: no cover - interfaz
        return ScanResult("unavailable", self.name, "Sin motor antivirus operativo")


def _creationflags() -> int:
    if sys.platform == "win32":
        return subprocess.BELOW_NORMAL_PRIORITY_CLASS | subprocess.CREATE_NO_WINDOW
    return 0


class DefenderScanner(Scanner):
    name = "Microsoft Defender (MpCmdRun)"

    def __init__(self) -> None:
        base = Path(os.environ.get("ProgramFiles", r"C:\Program Files"))
        self.exe = base / "Windows Defender" / "MpCmdRun.exe"

    def available(self) -> bool:
        return sys.platform == "win32" and self.exe.exists()

    def scan(self, path: Path) -> ScanResult:
        try:
            proc = subprocess.run(
                [str(self.exe), "-Scan", "-ScanType", "3", "-File", str(path.resolve()), "-DisableRemediation"],
                capture_output=True,
                text=True,
                timeout=get_settings().av_timeout_s,
                creationflags=_creationflags(),
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            return ScanResult("error", self.name, f"Fallo de ejecución: {type(e).__name__}")
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode == 0 and "found no threats" in out.lower():
            return ScanResult("clean", self.name, "Sin amenazas detectadas")
        if proc.returncode == 2:
            return ScanResult("infected", self.name, "Amenaza detectada")
        return ScanResult("error", self.name, f"Código de salida {proc.returncode}")


class ClamAVScanner(Scanner):
    name = "ClamAV"

    def __init__(self) -> None:
        self.exe = shutil.which("clamdscan") or shutil.which("clamscan")

    def available(self) -> bool:
        return self.exe is not None

    def scan(self, path: Path) -> ScanResult:
        try:
            proc = subprocess.run(
                [self.exe, "--no-summary", str(path.resolve())],
                capture_output=True,
                text=True,
                timeout=get_settings().av_timeout_s,
                creationflags=_creationflags(),
            )
        except (subprocess.TimeoutExpired, OSError) as e:
            return ScanResult("error", self.name, f"Fallo de ejecución: {type(e).__name__}")
        if proc.returncode == 0:
            return ScanResult("clean", self.name, "Sin amenazas detectadas")
        if proc.returncode == 1:
            return ScanResult("infected", self.name, "Amenaza detectada")
        return ScanResult("error", self.name, f"Código de salida {proc.returncode}")


class NoScanner(Scanner):
    name = "ninguno"

    def available(self) -> bool:
        return False

    def scan(self, path: Path) -> ScanResult:
        return ScanResult("unavailable", self.name, "No hay antivirus operativo: el archivo permanece bloqueado")


_override: Scanner | None = None


def set_scanner_override(scanner: Scanner | None) -> None:
    """Solo para pruebas automatizadas (dobles de prueba explícitos)."""
    global _override
    _override = scanner


def get_scanner() -> Scanner:
    if _override is not None:
        return _override
    engine = get_settings().av_engine.lower()
    candidates: list[Scanner]
    if engine == "defender":
        candidates = [DefenderScanner()]
    elif engine == "clamav":
        candidates = [ClamAVScanner()]
    elif engine == "none":
        candidates = []
    else:
        candidates = [DefenderScanner(), ClamAVScanner()]
    for c in candidates:
        if c.available():
            return c
    return NoScanner()
