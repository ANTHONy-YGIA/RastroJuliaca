"""Validación profunda y copias seguras de reproducción.

Las herramientas externas (FFmpeg/FFprobe) se ejecutan como procesos separados, sin
shell, con tiempo máximo, número de hilos limitado y prioridad baja.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

from PIL import Image, ImageOps

from ..config import get_settings
from .antivirus import _creationflags

Image.MAX_IMAGE_PIXELS = 60_000_000  # defensa contra bombas de descompresión


class MediaError(Exception):
    pass


def make_image_copy(src: Path, dst: Path) -> dict:
    try:
        with Image.open(src) as im:
            im.verify()
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im)
            w, h = im.size
            im = im.convert("RGB")
            im.thumbnail((1920, 1920))
            im.save(dst, "JPEG", quality=85, optimize=True)  # se descartan EXIF/GPS
    except (Image.DecompressionBombError, OSError, SyntaxError, ValueError) as e:
        raise MediaError(f"Imagen inválida o corrupta: {type(e).__name__}") from e
    return {"width": w, "height": h}


ACTIVE_PDF = re.compile(rb"/(JavaScript|JS|Launch|EmbeddedFile|OpenAction|AA|RichMedia|XFA)\b")


def check_pdf(src: Path) -> dict:
    data = src.read_bytes()
    if not data.startswith(b"%PDF-"):
        raise MediaError("No es un PDF válido")
    if b"%%EOF" not in data[-2048:]:
        raise MediaError("PDF incompleto o malformado")
    m = ACTIVE_PDF.search(data)
    if m:
        raise MediaError(f"El PDF contiene contenido activo no permitido ({m.group(1).decode()})")
    return {"pages_hint": data.count(b"/Type /Page") or data.count(b"/Type/Page")}


def probe_video(src: Path) -> dict:
    s = get_settings()
    ffprobe = s.resolved_ffprobe()
    if not ffprobe:
        raise MediaError("FFprobe no disponible")
    try:
        proc = subprocess.run(
            [ffprobe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(src)],
            capture_output=True,
            timeout=60,
            creationflags=_creationflags(),
        )
    except subprocess.TimeoutExpired as e:
        raise MediaError("FFprobe excedió el tiempo máximo") from e
    if proc.returncode != 0:
        raise MediaError("El video no pudo analizarse (formato inválido)")
    info = json.loads(proc.stdout or b"{}")
    vstreams = [st for st in info.get("streams", []) if st.get("codec_type") == "video"]
    if not vstreams:
        raise MediaError("El archivo no contiene una pista de video")
    duration = float(info.get("format", {}).get("duration") or 0)
    if duration > s.max_video_seconds:
        raise MediaError(f"El video supera la duración máxima de {s.max_video_seconds} s")
    v = vstreams[0]
    return {
        "duration_s": round(duration, 2),
        "width": v.get("width"),
        "height": v.get("height"),
        "codec": v.get("codec_name"),
        "has_audio": any(st.get("codec_type") == "audio" for st in info.get("streams", [])),
    }


def make_video_copy(src: Path, dst: Path) -> None:
    s = get_settings()
    ffmpeg = s.resolved_ffmpeg()
    if not ffmpeg:
        raise MediaError("FFmpeg no disponible")
    cmd = [
        ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-i", str(src),
        "-map", "0:v:0", "-map", "0:a:0?",
        "-vf", "scale=-2:'min(480,ih)'",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "28", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k",
        "-map_metadata", "-1", "-movflags", "+faststart",
        "-t", str(s.max_video_seconds),
        "-threads", str(s.media_threads),
        str(dst),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=s.media_timeout_s, creationflags=_creationflags())
    except subprocess.TimeoutExpired as e:
        dst.unlink(missing_ok=True)
        raise MediaError("La conversión excedió el tiempo máximo") from e
    if proc.returncode != 0 or not dst.exists():
        dst.unlink(missing_ok=True)
        raise MediaError("No se pudo generar la copia de reproducción")
