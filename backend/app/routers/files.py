"""Acceso autenticado, autorizado y auditado a archivos. Nunca se sirven archivos en cuarentena."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit
from ..db import get_db
from ..deps import get_current_user, get_case_for_reviewer
from ..models import FileStatus, Role, StoredFile, SupportingDocument, User
from ..serializers import file_out
from ..services import storage

router = APIRouter(prefix="/api/files", tags=["archivos"])


def _authorize(db: Session, sf: StoredFile | None, user: User) -> StoredFile:
    if not sf:
        raise HTTPException(404, "Archivo no encontrado")
    if user.role == Role.REVISOR.value:
        get_case_for_reviewer(db, sf.case_id, user)
        return sf
    if user.role == Role.DENUNCIANTE.value and sf.purpose == "RESPALDO":
        doc = db.scalar(select(SupportingDocument).where(SupportingDocument.file_id == sf.id))
        if doc and doc.case.reporter_id == user.id:
            return sf
    # Administración técnica no implica acceso a evidencias; colaboradores no descargan archivos
    raise HTTPException(404, "Archivo no encontrado")


@router.get("/{file_id}/meta")
def file_meta(file_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return file_out(_authorize(db, db.get(StoredFile, file_id), user))


@router.get("/{file_id}/content")
def file_content(
    file_id: str,
    request: Request,
    variant: Literal["playback", "original"] = "playback",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    sf = _authorize(db, db.get(StoredFile, file_id), user)
    if sf.status != FileStatus.DISPONIBLE.value:
        raise HTTPException(409, "El archivo no está disponible: permanece bloqueado hasta superar la validación")
    if variant == "playback":
        if not sf.playback_name:
            raise HTTPException(404, "No existe copia de reproducción para este archivo")
        path = storage.path_in("playback", sf.playback_name)
        media = "video/mp4" if sf.playback_name.endswith(".mp4") else "image/jpeg"
        disposition = "inline"
        name = f"{sf.id}-reproduccion{path.suffix}"
    else:
        path = storage.path_in("vault", sf.internal_name)
        media = storage.MIME_FOR_TYPE.get(sf.detected_type or "", "application/octet-stream")
        disposition = "attachment"
        name = f"{sf.id}{storage.EXT_FOR_TYPE.get(sf.detected_type or '', '')}"
    if not path.exists():
        raise HTTPException(404, "Archivo no disponible en el almacén")
    audit(db, "FILE_DOWNLOADED" if variant == "original" else "FILE_VIEWED", user, "file", sf.id, request, variant=variant, case_id=sf.case_id)
    db.commit()
    return FileResponse(
        path,
        media_type=media,
        headers={
            "Content-Disposition": f'{disposition}; filename="{name}"',
            "Cache-Control": "no-store, private",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )
