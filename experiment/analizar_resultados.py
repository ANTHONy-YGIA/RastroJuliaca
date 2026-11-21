"""Análisis descriptivo de los resultados REALES registrados en experiment/resultados/sesiones.csv.

  .\\scripts\\py.ps1 experiment\\analizar_resultados.py

Calcula por escenario y tarea: n, media, mediana y desviación estándar del tiempo; tasa de tareas
completadas; errores de asociación; incidencias de usabilidad; y diferencias pareadas A−B por participante.
Si no hay datos suficientes lo indica explícitamente. No genera ni imputa valores.
Escribe un resumen en experiment/resultados/resumen.json.
"""
from __future__ import annotations

import csv
import json
import statistics as st
from collections import defaultdict
from pathlib import Path

RES = Path(__file__).resolve().parent / "resultados"
CSV = RES / "sesiones.csv"


def desc(values: list[float]) -> dict:
    if not values:
        return {"n": 0}
    out = {"n": len(values), "media": round(st.mean(values), 2), "mediana": round(st.median(values), 2)}
    out["desv_est"] = round(st.stdev(values), 2) if len(values) > 1 else None
    return out


def main():
    if not CSV.exists():
        print("Sin datos: aún no existe experiment/resultados/sesiones.csv. Ejecute sesiones reales con registrar_sesion.py.")
        return
    rows = list(csv.DictReader(CSV.open(encoding="utf-8")))
    if not rows:
        print("Sin datos registrados.")
        return
    by = defaultdict(list)
    for r in rows:
        by[(r["escenario"], r["tarea"])].append(r)
    resumen = {"filas": len(rows), "participantes": sorted({r["participante"] for r in rows}), "por_escenario_tarea": {}, "pareado": {}}
    for (esc, tarea), rs in sorted(by.items()):
        resumen["por_escenario_tarea"][f"{esc}-{tarea}"] = {
            "tiempo_s": desc([float(r["segundos"]) for r in rs]),
            "completadas": f"{sum(int(r['completada']) for r in rs)}/{len(rs)}",
            "errores_asociacion_total": sum(int(r["errores_asociacion"]) for r in rs),
            "incidencias_usabilidad_total": sum(int(r["incidencias_usabilidad"]) for r in rs),
            "aciertos": f"{sum(int(r['evidencias_relevantes_identificadas']) for r in rs)}/{sum(int(r['evidencias_relevantes_esperadas']) for r in rs)}",
        }
    # Diferencias pareadas (mismo participante, misma tarea, ambos escenarios)
    times = {(r["participante"], r["tarea"], r["escenario"]): float(r["segundos"]) for r in rows}
    for tarea in sorted({r["tarea"] for r in rows}):
        diffs = [times[(p, tarea, "A")] - times[(p, tarea, "B")] for p in resumen["participantes"]
                 if (p, tarea, "A") in times and (p, tarea, "B") in times]
        resumen["pareado"][tarea] = {"diferencia_A_menos_B_s": desc(diffs),
                                     "nota": "Datos insuficientes para inferencia" if len(diffs) < 5 else "Considere prueba de Wilcoxon de rangos con signo"}
    RES.mkdir(exist_ok=True)
    (RES / "resumen.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(resumen, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
