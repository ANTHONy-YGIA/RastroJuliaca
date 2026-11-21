"""Pipeline de validación de archivos:

  1. Recepción en cuarentena (nombre interno aleatorio, hash SHA-256, límite de tamaño).
  2. Validación de formato por firma binaria según el uso permitido.
  3. Análisis antivirus real (si no hay motor: BLOQUEADO_SIN_ANTIVIRUS).
  4. Validación profunda y copia segura de reproducción (imágenes/videos re-codificados, sin metadatos).
  5. Traslado al almacén y disponibilidad para usuarios autorizados.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timezone

from fastapi import BackgroundTasks, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit, case_event, notify
from ..config import get_settings
from ..db import SessionLocal
from ..models import (
    CaseAssignment,
    Contribution,
    ContributionStatus,
    FileStatus,
    StoredFile,
    User,
)
from . import storage
from .antivirus import get_scanner
from .media import MediaError, check_pdf, make_image_copy, make_video_copy, probe_video

log = logging.getLogger("rastrojuliaca.pipeline")

ALLOWED = {
    "RESPALDO": {"jpeg", "png", "webp", "pdf", "mp4", "mov", "webm"},
    "FOTO": {"jpeg", "png", "webp"},
    "VIDEO": {"mp4", "mov", "webm"},
    "DOCUMENTO": {"pdf"},
}


def classes_for(allowed: set[str]) -> set[str]:
    return {storage.TYPE_CLASS[t] for t in allowed}


async def receive_upload(
    db: Session,
    upload: UploadFile,
    *,
    case_id: int,
    purpose: str,
    allowed_key: str,
    user: User,
) -> StoredFile:
    allowed = ALLOWED[allowed_key]
    saved = await storage.save_to_quarantine(upload, storage.max_limit_bytes(classes_for(allowed)))
    qpath = storage.path_in("quarantine", saved.internal_name)
    detected = storage.detect_type(qpath)
    if detected not in allowed:
        qpath.unlink(missing_ok=True)
        raise HTTPException(
            status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            "Formato no permitido o contenido no coincide con un formato autorizado",
        )
    mclass = storage.TYPE_CLASS[detected]
    if saved.size > storage.class_limit_bytes(mclass):
        qpath.unlink(missing_ok=True)
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, "El archivo supera el límite para su tipo")

    dup = db.scalar(
        select(StoredFile).where(
            StoredFile.case_id == case_id,
            StoredFile.sha256 == saved.sha256,
            StoredFile.status != FileStatus.ELIMINADO.value,
        )
    )
    sf = StoredFile(
        case_id=case_id,
        purpose=purpose,
        original_name=saved.original_name,
        internal_name=saved.internal_name,
        detected_type=detected,
        media_class=mclass,
        size_bytes=saved.size,
        sha256=saved.sha256,
        status=FileStatus.CUARENTENA.value,
        status_detail="En cuarentena, pendiente de análisis",
        duplicate_of_id=dup.id if dup else None,
        uploaded_by=user.id,
    )
    db.add(sf)
    db.flush()
    audit(db, "FILE_RECEIVED", user, "file", sf.id, case_id=case_id, sha256=sf.sha256, size=sf.size_bytes, type=detected)
    return sf


def schedule_processing(background: BackgroundTasks, file_id: str) -> None:
    if get_settings().process_files_inline:
        process_file(file_id)
    else:
        background.add_task(process_file, file_id)


def process_file(file_id: str) -> None:
    db = SessionLocal()
    try:
        sf = db.get(StoredFile, file_id)
        if not sf or sf.status not in (FileStatus.CUARENTENA.value, FileStatus.BLOQUEADO_SIN_ANTIVIRUS.value, FileStatus.ERROR_PROCESAMIENTO.value):
            return
        _run(db, sf)
        _propagate(db, sf)
        db.commit()
    except Exception:  # pragma: no cover - protección de último recurso
        log.exception("Error procesando archivo %s", file_id)
        db.rollback()
    finally:
        db.close()


def _run(db: Session, sf: StoredFile) -> None:
    qpath = storage.path_in("quarantine", sf.internal_name)
    if not qpath.exists():
        sf.status = FileStatus.ERROR_PROCESAMIENTO.value
        sf.status_detail = "El archivo en cuarentena no existe"
        return

    scanner = get_scanner()
    result = scanner.scan(qpath)
    sf.scan_engine = result.engine
    sf.scanned_at = datetime.now(timezone.utc)
    audit(db, "FILE_SCANNED", None, "file", sf.id, engine=result.engine, result=result.status)

    if result.status == "unavailable":
        sf.status = FileStatus.BLOQUEADO_SIN_ANTIVIRUS.value
        sf.status_detail = result.detail
        return
    if result.status == "error":
        sf.status = FileStatus.ERROR_PROCESAMIENTO.value
        sf.status_detail = f"El análisis antivirus no pudo completarse ({result.detail}). Archivo bloqueado."
        return
    if result.status == "infected":
        sf.status = FileStatus.INFECTADO.value
        sf.status_detail = "Amenaza detectada. Archivo eliminado."
        qpath.unlink(missing_ok=True)
        return

    # Antivirus limpio -> validación profunda y copia de reproducción
    playback_name = None
    try:
        if sf.media_class == "image":
            playback_name = secrets.token_hex(16) + ".jpg"
            sf.media_info = make_image_copy(qpath, storage.path_in("playback", playback_name))
        elif sf.media_class == "video":
            sf.media_info = probe_video(qpath)
            playback_name = secrets.token_hex(16) + ".mp4"
            make_video_copy(qpath, storage.path_in("playback", playback_name))
        elif sf.media_class == "document":
            sf.media_info = check_pdf(qpath)
    except MediaError as e:
        if playback_name:
            storage.path_in("playback", playback_name).unlink(missing_ok=True)
        if "no disponible" in str(e):
            sf.status = FileStatus.ERROR_PROCESAMIENTO.value
            sf.status_detail = f"{e}. El archivo permanece bloqueado hasta poder validarlo."
            return
        sf.status = FileStatus.RECHAZADO_FORMATO.value
        sf.status_detail = str(e)
        qpath.unlink(missing_ok=True)
        return

    qpath.replace(storage.path_in("vault", sf.internal_name))
    sf.playback_name = playback_name
    sf.status = FileStatus.DISPONIBLE.value
    sf.status_detail = "Validado: antivirus sin amenazas y formato verificado"


def _propagate(db: Session, sf: StoredFile) -> None:
    contrib = db.scalar(select(Contribution).where(Contribution.file_id == sf.id))
    if not contrib:
        return
    if sf.status == FileStatus.DISPONIBLE.value:
        contrib.status = ContributionStatus.PENDIENTE_REVISION.value
        case_event(db, contrib.case_id, "APORTACION_VALIDADA", f"{contrib.code}: archivo validado, pendiente de revisión", visible_to_reporter=False)
        for a in db.scalars(select(CaseAssignment).where(CaseAssignment.case_id == contrib.case_id, CaseAssignment.active.is_(True))):
            notify(db, a.reviewer_id, "Nueva evidencia pendiente", f"{contrib.code} lista para revisión", f"/revisor/aportaciones/{contrib.id}")
    else:
        contrib.status = ContributionStatus.BLOQUEADA.value
        case_event(db, contrib.case_id, "APORTACION_BLOQUEADA", f"{contrib.code}: {sf.status}", visible_to_reporter=False)
    notify(db, contrib.contributor_id, "Estado de su aportación actualizado", f"{contrib.code}: {contrib.status}", "/mis-aportaciones")
