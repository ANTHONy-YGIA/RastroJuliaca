"""Almacenamiento seguro de archivos fuera del directorio público.

Estructura (bajo RJ_STORAGE_DIR):
  quarantine/  archivos recién recibidos, nunca servidos
  vault/       originales validados (solo acceso autenticado, autorizado y auditado)
  playback/    copias seguras de reproducción (re-codificadas, sin metadatos)
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
from dataclasses import dataclass
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from ..config import get_settings

CHUNK = 1024 * 1024

# Tipo detectado -> clase multimedia
TYPE_CLASS = {
    "jpeg": "image",
    "png": "image",
    "webp": "image",
    "pdf": "document",
    "mp4": "video",
    "mov": "video",
    "webm": "video",
}
EXT_FOR_TYPE = {"jpeg": ".jpg", "png": ".png", "webp": ".webp", "pdf": ".pdf", "mp4": ".mp4", "mov": ".mov", "webm": ".webm"}
MIME_FOR_TYPE = {
    "jpeg": "image/jpeg",
    "png": "image/png",
    "webp": "image/webp",
    "pdf": "application/pdf",
    "mp4": "video/mp4",
    "mov": "video/quicktime",
    "webm": "video/webm",
}


def dirs() -> dict[str, Path]:
    root = Path(get_settings().storage_dir)
    out = {name: root / name for name in ("quarantine", "vault", "playback")}
    for p in out.values():
        p.mkdir(parents=True, exist_ok=True)
    return out


def path_in(area: str, internal_name: str) -> Path:
    if not re.fullmatch(r"[a-f0-9]{32}(\.[a-z0-9]{2,5})?", internal_name):
        raise ValueError("nombre interno inválido")
    return dirs()[area] / internal_name


def class_limit_bytes(media_class: str) -> int:
    s = get_settings()
    return {"image": s.max_image_mb, "video": s.max_video_mb, "document": s.max_document_mb}[media_class] * 1024 * 1024


def max_limit_bytes(classes: set[str]) -> int:
    return max(class_limit_bytes(c) for c in classes)


def sanitize_filename(name: str | None) -> str:
    name = os.path.basename(name or "archivo")
    name = re.sub(r"[^\w.\- ()áéíóúÁÉÍÓÚñÑ]", "_", name)[:150]
    return name or "archivo"


@dataclass
class SavedUpload:
    internal_name: str
    size: int
    sha256: str
    original_name: str


async def save_to_quarantine(upload: UploadFile, max_bytes: int) -> SavedUpload:
    internal = secrets.token_hex(16)
    dest = dirs()["quarantine"] / internal
    h = hashlib.sha256()
    size = 0
    try:
        with open(dest, "xb") as out:
            while True:
                chunk = await upload.read(CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(
                        status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        f"El archivo supera el límite de {max_bytes // (1024 * 1024)} MB",
                    )
                h.update(chunk)
                out.write(chunk)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    if size == 0:
        dest.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "El archivo está vacío")
    return SavedUpload(internal, size, h.hexdigest(), sanitize_filename(upload.filename))


def detect_type(path: Path) -> str | None:
    """Detección por firma binaria (no se confía en la extensión ni en el Content-Type)."""
    with open(path, "rb") as f:
        head = f.read(64)
    if head.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    if head.startswith(b"%PDF-"):
        return "pdf"
    if head.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm"
    if head[4:8] == b"ftyp":
        brand = head[8:12]
        if brand == b"qt  ":
            return "mov"
        return "mp4"
    return None


def delete_physical(internal_name: str | None, playback_name: str | None = None) -> None:
    for area in ("quarantine", "vault"):
        if internal_name:
            try:
                path_in(area, internal_name).unlink(missing_ok=True)
            except ValueError:
                pass
    if playback_name:
        try:
            path_in("playback", playback_name).unlink(missing_ok=True)
        except ValueError:
            pass
