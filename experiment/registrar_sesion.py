"""Cronómetro de sesión para el facilitador. Registra mediciones REALES en experiment/resultados/sesiones.csv.

  .\\scripts\\py.ps1 experiment\\registrar_sesion.py --participante P01 --escenario A --conjunto C1 --orden AB

Para cada tarea: Enter para iniciar, Enter al terminar; luego se ingresan los datos observados
(evidencias correctas, errores de asociación, incidencias de usabilidad). No se generan valores automáticamente.
"""
from __future__ import annotations

import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

RES = Path(__file__).resolve().parent / "resultados"
CSV = RES / "sesiones.csv"
COLUMNS = ["participante", "orden", "escenario", "conjunto", "tarea", "inicio_iso", "segundos", "completada",
           "evidencias_relevantes_identificadas", "evidencias_relevantes_esperadas", "errores_asociacion",
           "incidencias_usabilidad", "observaciones"]

TAREAS = [
    ("T1", "Localizar todas las evidencias relevantes del expediente E1", 3),
    ("T2", "Localizar todas las evidencias relevantes del expediente E2", 3),
    ("T3", "Identificar la evidencia más cercana en tiempo al incidente E3", 1),
    ("T4", "Detectar evidencias duplicadas en todo el conjunto", 2),
    ("T5", "Preparar un informe del expediente E1 con evidencias, horas y huellas/identificadores", 3),
]


def ask_int(msg: str) -> int:
    while True:
        v = input(msg).strip()
        if v.isdigit():
            return int(v)
        print("Ingrese un número entero.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--participante", required=True)
    ap.add_argument("--escenario", choices=["A", "B"], required=True)
    ap.add_argument("--conjunto", choices=["C1", "C2"], required=True)
    ap.add_argument("--orden", choices=["AB", "BA"], required=True)
    a = ap.parse_args()
    RES.mkdir(exist_ok=True)
    new = not CSV.exists()
    with CSV.open("a", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        for code, desc, esperado in TAREAS:
            print(f"\n[{code}] {desc}")
            input("  Enter para INICIAR…")
            t0 = time.perf_counter()
            start = datetime.now().isoformat(timespec="seconds")
            input("  Enter al TERMINAR (o cuando el participante abandone)…")
            secs = round(time.perf_counter() - t0, 1)
            completada = input("  ¿Tarea completada? (s/n): ").strip().lower().startswith("s")
            correctas = ask_int(f"  Evidencias relevantes identificadas correctamente (esperadas {esperado}): ")
            errores = ask_int("  Errores de asociación (evidencia asignada al expediente equivocado): ")
            incid = ask_int("  Incidencias de usabilidad observadas: ")
            obs = input("  Observaciones (opcional): ").strip()
            w.writerow({"participante": a.participante, "orden": a.orden, "escenario": a.escenario, "conjunto": a.conjunto, "tarea": code,
                        "inicio_iso": start, "segundos": secs, "completada": int(completada), "evidencias_relevantes_identificadas": correctas,
                        "evidencias_relevantes_esperadas": esperado, "errores_asociacion": errores, "incidencias_usabilidad": incid,
                        "observaciones": obs})
            fh.flush()
            print(f"  Registrado: {secs} s")
    print(f"\nSesión guardada en {CSV}")


if __name__ == "__main__":
    main()
