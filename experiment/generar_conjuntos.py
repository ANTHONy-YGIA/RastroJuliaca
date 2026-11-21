"""Genera dos conjuntos EQUIVALENTES de evidencias ficticias para el protocolo experimental.

Cada conjunto (C1 y C2) contiene la misma estructura: 3 expedientes ficticios y 18 evidencias
(imágenes sintéticas y descripciones) con igual proporción de evidencias relevantes, distractoras y
duplicadas, y con distancias/horas equivalentes. Solo cambian los detalles superficiales.

Salidas (bajo experiment/conjuntos/<C1|C2>/):
  escenario_a/         carpetas desorganizadas (nombres tipo mensajería, expedientes mezclados)
  clave_respuestas.json  verdad de referencia para puntuar (NO entregar a participantes)
  aportaciones.json      datos para cargar el mismo conjunto en RastroJuliaca (escenario B)

Uso:
  .\\scripts\\py.ps1 experiment\\generar_conjuntos.py
"""
from __future__ import annotations

import json
import random
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "conjuntos"
PE = timezone(timedelta(hours=-5))
BASE = (-15.4990, -70.1330)

# Plantilla común: (expediente, relevante, distancia_aprox_km, minutos_desde_incidente, duplicado_de)
TEMPLATE = [
    ("E1", True, 0.3, 15, None), ("E1", True, 0.8, 40, None), ("E1", False, 6.0, 600, None), ("E1", False, None, None, None),
    ("E1", True, 1.2, 70, None), ("E1", False, 0.5, 15, 1),
    ("E2", True, 0.2, 5, None), ("E2", True, 1.0, 30, None), ("E2", False, 9.0, 1440, None), ("E2", False, None, 120, None),
    ("E2", True, 0.6, 20, None), ("E2", False, 0.2, 5, 7),
    ("E3", True, 0.4, 10, None), ("E3", False, 4.0, 300, None), ("E3", True, 0.9, 45, None), ("E3", False, None, None, None),
    ("E3", True, 1.5, 90, None), ("E3", False, 2.5, 200, None),
]

VARIANTES = {
    "C1": {
        "E1": ("robo-vehiculos", "Motocicleta azul sustraída", "Zona Norte", "2026-10-03T22:10:00"),
        "E2": ("accidentes-transito", "Choque en intersección", "Centro de Juliaca", "2026-10-05T18:40:00"),
        "E3": ("objetos-extraviados", "Maletín negro extraviado", "Mercados y comercio", "2026-10-07T09:15:00"),
    },
    "C2": {
        "E1": ("robo-vehiculos", "Mototaxi verde sustraída", "Zona Sur", "2026-10-10T21:50:00"),
        "E2": ("accidentes-transito", "Atropello en avenida", "Salida a Puno", "2026-10-12T17:20:00"),
        "E3": ("objetos-extraviados", "Mochila roja extraviada", "Zona Este", "2026-10-14T08:45:00"),
    },
}

DESCRIPCIONES_REL = ["Se observa un vehículo similar al descrito", "Registro de cámara con hora cercana", "Imagen del lugar minutos después",
                     "Persona con objeto similar", "Vista de la calle con el vehículo"]
DESCRIPCIONES_NO = ["Imagen de otra calle sin relación", "Registro de un día distinto", "Fotografía borrosa sin elementos útiles",
                    "Captura reenviada sin contexto"]


def offset(km: float | None, rng: random.Random):
    if km is None:
        return None, None
    ang = rng.uniform(0, 6.283)
    import math

    return round(BASE[0] + (km / 111.0) * math.sin(ang), 6), round(BASE[1] + (km / 107.0) * math.cos(ang), 6)


def image(path: Path, seed: int, label: str):
    rng = random.Random(seed)
    im = Image.new("RGB", (640, 420), (rng.randint(30, 120), rng.randint(30, 120), rng.randint(30, 120)))
    d = ImageDraw.Draw(im)
    for _ in range(12):
        x, y = rng.randint(0, 600), rng.randint(60, 400)
        d.rectangle([x, y, x + rng.randint(20, 120), y + rng.randint(10, 60)], fill=(rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)))
    d.rectangle([0, 0, 640, 40], fill=(11, 37, 69))
    d.text((10, 12), "IMAGEN SINTETICA - EXPERIMENTO RASTROJULIACA", fill=(255, 255, 255))
    d.text((10, 50), label, fill=(255, 255, 255))
    im.save(path, "JPEG", quality=80)


def generar(nombre: str, seed: int):
    rng = random.Random(seed)
    base = OUT / nombre
    if base.exists():
        shutil.rmtree(base)
    esc_a = base / "escenario_a"
    esc_a.mkdir(parents=True)
    # Estructura desorganizada típica: varias carpetas de mensajería y descargas mezcladas
    carpetas = ["WhatsApp Images", "Descargas", "Grupo vecinal", "Enviados por correo", "Varios"]
    for c in carpetas:
        (esc_a / c).mkdir()
    clave = {"conjunto": nombre, "expedientes": {}, "evidencias": []}
    aportes = []
    paths = {}
    for e, (cat, titulo, zona, inc) in VARIANTES[nombre].items():
        clave["expedientes"][e] = {"categoria": cat, "titulo": titulo, "zona": zona, "incidente": inc, "lat": BASE[0], "lon": BASE[1]}
    for i, (exp, rel, km, mins, dup) in enumerate(TEMPLATE, start=1):
        inc = datetime.fromisoformat(VARIANTES[nombre][exp][3]).replace(tzinfo=PE)
        declared = (inc + timedelta(minutes=mins)).isoformat() if mins is not None else None
        lat, lon = offset(km, rng)
        desc = rng.choice(DESCRIPCIONES_REL if rel else DESCRIPCIONES_NO)
        fecha_nombre = (inc + timedelta(days=rng.randint(0, 2))).strftime("%Y%m%d")
        fname = f"IMG-{fecha_nombre}-WA{rng.randint(1000, 9999)}.jpg"
        carpeta = rng.choice(carpetas)
        dest = esc_a / carpeta / fname
        if dup:
            shutil.copyfile(paths[dup], dest)
        else:
            image(dest, seed * 100 + i, f"{desc} ({nombre}-{i:02d})")
        paths[i] = dest
        # Metadatos sueltos como en la práctica: un .txt con lo que dijo quien envió la imagen
        (dest.with_suffix(".txt")).write_text(
            f"Mensaje recibido (sobre: {VARIANTES[nombre][exp][1].lower()}): {desc}. Hora aprox: {declared or 'no indicó'}. "
            f"Ubicación: {f'{lat}, {lon}' if lat else 'no indicó'}.\n",
            encoding="utf-8",
        )
        clave["evidencias"].append({"id": i, "archivo": str(dest.relative_to(base)), "expediente": exp, "relevante": rel,
                                    "duplicado_de": dup, "distancia_km": km, "minutos_desde_incidente": mins})
        aportes.append({"id": i, "expediente": exp, "archivo": str(dest.relative_to(base)), "descripcion": desc,
                        "declared_at": declared, "lat": lat, "lon": lon, "certeza": rng.choice(["ALTA", "MEDIA", "BAJA"])})
    (base / "clave_respuestas.json").write_text(json.dumps(clave, ensure_ascii=False, indent=2), encoding="utf-8")
    (base / "aportaciones.json").write_text(json.dumps({"expedientes": clave["expedientes"], "aportes": aportes}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{nombre}: {len(aportes)} evidencias en {esc_a}")


if __name__ == "__main__":
    generar("C1", 101)
    generar("C2", 202)
    print("Listo. Entregue a los participantes solo la carpeta escenario_a; conserve clave_respuestas.json.")
