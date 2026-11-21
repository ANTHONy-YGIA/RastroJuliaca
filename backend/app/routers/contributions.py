"""Aportaciones ciudadanas: envío a expedientes habilitados y seguimiento privado."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit, case_event, notify
from ..config import get_settings
from ..db import get_db
from ..deps import require_citizen
from ..models import Case, CaseAssignment, Certainty, Contribution, ContributionStatus, ContributionType, Correction, User
from ..ratelimit import limiter
from ..security import as_aware, iso
from ..serializers import contribution_out
from ..services import pipeline
from ..services.geo import valid_coords
from ..services.policies import accepts_contributions

router = APIRouter(prefix="/api/contributions", tags=["aportaciones"])

CORRECTABLE = {"declared_at", "declared_lat", "declared_lon", "description"}


def _parse_optional_float(v: str | None, name: str) -> float | None:
    if v is None or v.strip() == "":
        return None
    try:
        return float(v)
    except ValueError:
        raise HTTPException(422, f"{name} debe ser numérico") from None


def _parse_declared(v: str | None) -> datetime | None:
    if not v:
        return None
    try:
        dt = as_aware(datetime.fromisoformat(v))
    except ValueError:
        raise HTTPException(422, "Fecha y hora declaradas no válidas") from None
    if dt > datetime.now(timezone.utc) + timedelta(minutes=10):
        raise HTTPException(422, "La fecha declarada no puede estar en el futuro")
    return dt


@router.post("", status_code=201)
async def create_contribution(
    request: Request,
    background: BackgroundTasks,
    case_code: str = Form(..., max_length=30),
    ctype: str = Form(...),
    description: str = Form(..., min_length=10, max_length=3000),
    certainty: str = Form(...),
    declared_at: str | None = Form(default=None),
    declared_lat: str | None = Form(default=None),
    declared_lon: str | None = Form(default=None),
    location_note: str | None = Form(default=None, max_length=255),
    file: UploadFile | None = File(default=None),
    user: User = Depends(require_citizen),
    db: Session = Depends(get_db),
):
    s = get_settings()
    limiter.check(f"upload:{user.id}", s.rate_upload, s.rate_window_s)
    if ctype not in ContributionType.__members__:
        raise HTTPException(422, "Tipo de aportación no válido")
    if certainty not in Certainty.__members__:
        raise HTTPException(422, "Nivel de certeza no válido")
    case = db.scalar(select(Case).where(Case.code == case_code))
    if not case or not accepts_contributions(case):
        # No se distingue entre inexistente y no habilitado
        raise HTTPException(404, "Expediente no disponible para aportaciones")
    lat = _parse_optional_float(declared_lat, "Latitud")
    lon = _parse_optional_float(declared_lon, "Longitud")
    if not valid_coords(lat, lon):
        raise HTTPException(422, "Coordenadas incompletas o fuera de rango")
    when = _parse_declared(declared_at)
    has_file = file is not None and (file.filename or "") != ""
    if ctype == ContributionType.TEXTO.value and has_file:
        raise HTTPException(422, "Las aportaciones de texto no admiten archivos")
    if ctype != ContributionType.TEXTO.value and not has_file:
        raise HTTPException(422, "Debe adjuntar el archivo de la aportación")

    contrib = Contribution(
        code="tmp",
        case_id=case.id,
        contributor_id=user.id,
        ctype=ctype,
        description=description.strip(),
        declared_at=when,
        declared_lat=lat,
        declared_lon=lon,
        location_note=(location_note or "").strip() or None,
        certainty=certainty,
        status=ContributionStatus.PENDIENTE_REVISION.value if ctype == ContributionType.TEXTO.value else ContributionStatus.EN_VALIDACION.value,
    )
    sf = None
    if has_file:
        sf = await pipeline.receive_upload(db, file, case_id=case.id, purpose="EVIDENCIA", allowed_key=ctype, user=user)
        contrib.file_id = sf.id
    db.add(contrib)
    db.flush()
    contrib.code = f"AP-{datetime.now(timezone.utc).year}-{contrib.id:05d}"
    case_event(db, case.id, "APORTACION_RECIBIDA", f"{contrib.code} ({ctype}) recibida", None, visible_to_reporter=False)
    audit(db, "CONTRIBUTION_CREATED", user, "contribution", contrib.id, request, case_id=case.id, type=ctype, sha256=sf.sha256 if sf else None)
    if not sf:
        for a in db.scalars(select(CaseAssignment).where(CaseAssignment.case_id == case.id, CaseAssignment.active.is_(True))):
            notify(db, a.reviewer_id, "Nueva información pendiente", f"{contrib.code} lista para revisión", f"/revisor/aportaciones/{contrib.id}")
    db.commit()
    if sf:
        pipeline.schedule_processing(background, sf.id)
        db.expire_all()
    contrib = db.get(Contribution, contrib.id)
    return contribution_out(db, contrib, view="contributor")


@router.get("/mine")
def my_contributions(user: User = Depends(require_citizen), db: Session = Depends(get_db)):
    items = db.scalars(select(Contribution).where(Contribution.contributor_id == user.id).order_by(Contribution.created_at.desc())).all()
    return [contribution_out(db, c, view="contributor") for c in items]


def _own(db: Session, cid: int, user: User) -> Contribution:
    c = db.get(Contribution, cid)
    if not c or c.contributor_id != user.id:
        raise HTTPException(404, "Aportación no encontrada")
    return c


@router.get("/{cid}")
def get_contribution(cid: int, user: User = Depends(require_citizen), db: Session = Depends(get_db)):
    return contribution_out(db, _own(db, cid, user), view="contributor")


class CorrectionIn(BaseModel):
    field: Literal["declared_at", "declared_lat", "declared_lon", "description"]
    new_value: str | None = Field(default=None, max_length=3000)
    reason: str = Field(min_length=10, max_length=1000)


def apply_correction(db: Session, c: Contribution, body: CorrectionIn, author: User) -> Correction:
    """Registra una corrección justificada. El dato original de la aportación no se modifica."""
    from ..serializers import corrections_for, effective_values

    current = effective_values(c, corrections_for(db, c.id))
    nv = (body.new_value or "").strip() or None
    if body.field == "declared_at" and nv:
        nv = iso(_parse_declared(nv))
    if body.field in ("declared_lat", "declared_lon") and nv:
        val = _parse_optional_float(nv, "Coordenada")
        lim = 90 if body.field == "declared_lat" else 180
        if not -lim <= val <= lim:
            raise HTTPException(422, "Coordenada fuera de rango")
        nv = str(val)
    if body.field == "description" and (not nv or len(nv) < 10):
        raise HTTPException(422, "La descripción corregida debe tener al menos 10 caracteres")
    old = current.get(body.field)
    corr = Correction(contribution_id=c.id, field=body.field, old_value=None if old is None else str(old), new_value=nv, reason=body.reason.strip(), author_id=author.id)
    db.add(corr)
    case_event(db, c.case_id, "CORRECCION", f"{c.code}: corrección de {body.field} ({body.reason.strip()[:80]})", author, visible_to_reporter=False)
    return corr


@router.post("/{cid}/corrections", status_code=201)
def correct_own(cid: int, body: CorrectionIn, request: Request, user: User = Depends(require_citizen), db: Session = Depends(get_db)):
    c = _own(db, cid, user)
    if c.status == ContributionStatus.CLASIFICADA.value:
        raise HTTPException(409, "La aportación ya fue clasificada; contacte al equipo de revisión")
    apply_correction(db, c, body, user)
    audit(db, "CONTRIBUTION_CORRECTED", user, "contribution", c.id, request, field=body.field)
    db.commit()
    return contribution_out(db, c, view="contributor")
