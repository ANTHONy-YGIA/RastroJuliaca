"""Expedientes del denunciante: creación, edición, documentación de respaldo y envío a revisión."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..audit import audit, case_event, notify
from ..config import get_settings
from ..db import get_db
from ..deps import get_case_for_owner, require_reporter, reviewer_cleared_for
from ..models import (
    Case,
    CaseAssignment,
    CaseStatus,
    Category,
    FileStatus,
    Role,
    SupportingDocument,
    User,
)
from ..ratelimit import limiter
from ..security import as_aware
from ..serializers import case_detail, case_summary, category_effective, document_out
from ..services import pipeline
from ..services.forms import FieldValidationError, validate_fields
from ..services.geo import valid_coords
from ..services.policies import PROTECTED_FLAGS, effective_sensitivity
from .public import DOC_TYPES, ZONES

router = APIRouter(prefix="/api/cases", tags=["expedientes"])

EDITABLE = {CaseStatus.BORRADOR.value, CaseStatus.CORRECCION_SOLICITADA.value}
BAD_FILE = {FileStatus.INFECTADO.value, FileStatus.RECHAZADO_FORMATO.value, FileStatus.ELIMINADO.value}


class CaseIn(BaseModel):
    category_id: int
    title: str = Field(min_length=5, max_length=160)
    description: str = Field(min_length=20, max_length=5000)
    incident_at: datetime
    zone: str
    private_lat: float | None = None
    private_lon: float | None = None
    private_location_note: str | None = Field(default=None, max_length=255)
    specific_fields: dict = Field(default_factory=dict)
    sensitive_flags: list[str] = Field(default_factory=list)

    @field_validator("zone")
    @classmethod
    def _zone(cls, v: str) -> str:
        if v not in ZONES:
            raise ValueError("Zona no válida")
        return v

    @field_validator("sensitive_flags")
    @classmethod
    def _flags(cls, v: list[str]) -> list[str]:
        bad = [f for f in v if f not in PROTECTED_FLAGS]
        if bad:
            raise ValueError("Marcador de sensibilidad no reconocido")
        return sorted(set(v))


class CaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=5, max_length=160)
    description: str | None = Field(default=None, min_length=20, max_length=5000)
    incident_at: datetime | None = None
    zone: str | None = None
    private_lat: float | None = None
    private_lon: float | None = None
    private_location_note: str | None = Field(default=None, max_length=255)
    specific_fields: dict | None = None
    sensitive_flags: list[str] | None = None


def _check_incident_time(dt: datetime) -> datetime:
    aware = as_aware(dt)
    if aware > datetime.now(timezone.utc) + timedelta(minutes=10):
        raise HTTPException(422, "La fecha del incidente no puede estar en el futuro")
    if aware < datetime.now(timezone.utc) - timedelta(days=365 * 5):
        raise HTTPException(422, "La fecha del incidente es demasiado antigua para este sistema")
    return aware


def _validate_specific(cat: Category, data: dict) -> dict:
    schema, _ = category_effective(cat)
    try:
        return validate_fields(schema, data)
    except FieldValidationError as e:
        raise HTTPException(422, {"message": "Campos específicos inválidos", "fields": e.errors}) from None


def _sensitivity(cat: Category, flags: list[str]) -> str:
    _, base = category_effective(cat)
    return effective_sensitivity(base, cat.min_sensitivity, None, flags)


@router.post("", status_code=201)
def create_case(body: CaseIn, request: Request, user: User = Depends(require_reporter), db: Session = Depends(get_db)):
    cat = db.get(Category, body.category_id)
    if not cat or not cat.active:
        raise HTTPException(422, "Categoría no válida")
    if not valid_coords(body.private_lat, body.private_lon):
        raise HTTPException(422, "Coordenadas incompletas o fuera de rango")
    fields = _validate_specific(cat, body.specific_fields)
    case = Case(
        code="tmp",
        category_id=cat.id,
        reporter_id=user.id,
        title=body.title.strip(),
        description=body.description.strip(),
        incident_at=_check_incident_time(body.incident_at),
        zone=body.zone,
        private_lat=body.private_lat,
        private_lon=body.private_lon,
        private_location_note=body.private_location_note,
        specific_fields=fields,
        sensitive_flags=body.sensitive_flags,
        sensitivity=_sensitivity(cat, body.sensitive_flags),
        status=CaseStatus.BORRADOR.value,
    )
    db.add(case)
    db.flush()
    case.code = f"RJ-{datetime.now(timezone.utc).year}-{case.id:05d}"
    case_event(db, case.id, "CREADO", "Expediente creado como borrador privado", user)
    audit(db, "CASE_CREATED", user, "case", case.id, request, sensitivity=case.sensitivity)
    db.commit()
    db.refresh(case)
    return case_detail(db, case, view="owner")


@router.get("/mine")
def my_cases(user: User = Depends(require_reporter), db: Session = Depends(get_db)):
    cases = db.scalars(select(Case).where(Case.reporter_id == user.id).order_by(Case.created_at.desc())).all()
    return [case_summary(c) for c in cases]


@router.get("/{case_id}")
def get_my_case(case_id: int, user: User = Depends(require_reporter), db: Session = Depends(get_db)):
    return case_detail(db, get_case_for_owner(db, case_id, user), view="owner")


@router.patch("/{case_id}")
def update_case(case_id: int, body: CaseUpdate, request: Request, user: User = Depends(require_reporter), db: Session = Depends(get_db)):
    case = get_case_for_owner(db, case_id, user)
    if case.status not in EDITABLE:
        raise HTTPException(409, "El expediente solo puede editarse en borrador o cuando se solicitan correcciones")
    data = body.model_dump(exclude_unset=True)
    if "zone" in data and data["zone"] not in ZONES:
        raise HTTPException(422, "Zona no válida")
    if "incident_at" in data and data["incident_at"]:
        data["incident_at"] = _check_incident_time(data["incident_at"])
    if "specific_fields" in data and data["specific_fields"] is not None:
        data["specific_fields"] = _validate_specific(case.category, data["specific_fields"])
    if "sensitive_flags" in data and data["sensitive_flags"] is not None:
        flags = sorted(set(data["sensitive_flags"]))
        if any(f not in PROTECTED_FLAGS for f in flags):
            raise HTTPException(422, "Marcador de sensibilidad no reconocido")
        # Las protecciones nunca se reducen: solo se pueden añadir marcadores
        flags = sorted(set(flags) | set(case.sensitive_flags or []))
        data["sensitive_flags"] = flags
        data["sensitivity"] = _sensitivity(case.category, flags)
    lat = data.get("private_lat", case.private_lat)
    lon = data.get("private_lon", case.private_lon)
    if not valid_coords(lat, lon):
        raise HTTPException(422, "Coordenadas incompletas o fuera de rango")
    for k, v in data.items():
        setattr(case, k, v)
    case_event(db, case.id, "EDITADO", "El denunciante actualizó la información", user)
    audit(db, "CASE_UPDATED", user, "case", case.id, request, fields=sorted(data.keys()))
    db.commit()
    return case_detail(db, case, view="owner")


@router.post("/{case_id}/documents", status_code=201)
async def upload_document(
    case_id: int,
    request: Request,
    background: BackgroundTasks,
    file: UploadFile = File(...),
    doc_type: str = Form(...),
    description: str = Form(default="", max_length=500),
    user: User = Depends(require_reporter),
    db: Session = Depends(get_db),
):
    s = get_settings()
    limiter.check(f"upload:{user.id}", s.rate_upload, s.rate_window_s)
    case = get_case_for_owner(db, case_id, user)
    if case.status not in EDITABLE | {CaseStatus.PENDIENTE_REVISION.value}:
        raise HTTPException(409, "No se pueden adjuntar documentos en el estado actual")
    if doc_type not in DOC_TYPES:
        raise HTTPException(422, "Tipo de documento no válido")
    sf = await pipeline.receive_upload(db, file, case_id=case.id, purpose="RESPALDO", allowed_key="RESPALDO", user=user)
    doc = SupportingDocument(case_id=case.id, doc_type=doc_type, description=description.strip(), file_id=sf.id)
    db.add(doc)
    case_event(db, case.id, "DOCUMENTO_ADJUNTO", f"{DOC_TYPES[doc_type]} recibido (en cuarentena)", user)
    db.commit()
    pipeline.schedule_processing(background, sf.id)
    db.refresh(doc)
    return document_out(doc)


def _check_document_policy(case: Case) -> list[str]:
    cat = case.category
    policy = dict((cat.parent.document_policy if cat.parent else {}) or {})
    policy.update(cat.document_policy or {})
    docs = [d for d in case.documents if d.file.status not in BAD_FILE]
    present = {d.doc_type for d in docs}
    problems = []
    min_docs = int(policy.get("min_documents", 1))
    if len(docs) < min_docs:
        problems.append(f"Se requieren al menos {min_docs} documento(s) de respaldo válidos")
    for group in policy.get("required_any", []):
        if not present.intersection(group):
            problems.append("Falta uno de: " + ", ".join(DOC_TYPES.get(g, g) for g in group))
    return problems


def auto_assign(db: Session, case: Case, actor: User | None) -> User | None:
    if any(a.active for a in case.assignments):
        return None
    reviewers = db.scalars(select(User).where(User.role == Role.REVISOR.value, User.is_active.is_(True))).all()
    eligible = [r for r in reviewers if reviewer_cleared_for(r, case.sensitivity)]
    if not eligible:
        for admin in db.scalars(select(User).where(User.role == Role.ADMIN.value, User.is_active.is_(True))):
            notify(db, admin.id, "Expediente sin revisor habilitado", f"{case.code} requiere asignación manual", "/admin")
        return None

    def load(r: User) -> int:
        return db.scalar(
            select(func.count(CaseAssignment.id))
            .join(Case, Case.id == CaseAssignment.case_id)
            .where(CaseAssignment.reviewer_id == r.id, CaseAssignment.active.is_(True), Case.status.in_([CaseStatus.PENDIENTE_REVISION.value, CaseStatus.APROBADO.value]))
        ) or 0

    chosen = min(eligible, key=lambda r: (load(r), r.id))
    case.assignments.append(CaseAssignment(reviewer_id=chosen.id, assigned_by=None))
    case_event(db, case.id, "ASIGNADO", f"Asignado automáticamente a {chosen.full_name}", None, visible_to_reporter=False)
    notify(db, chosen.id, "Nuevo expediente asignado", f"{case.code} pendiente de revisión", f"/revisor/expedientes/{case.id}")
    return chosen


@router.post("/{case_id}/submit")
def submit_case(case_id: int, request: Request, user: User = Depends(require_reporter), db: Session = Depends(get_db)):
    case = get_case_for_owner(db, case_id, user)
    if case.status not in EDITABLE:
        raise HTTPException(409, "El expediente ya fue enviado a revisión")
    _validate_specific(case.category, case.specific_fields or {})
    problems = _check_document_policy(case)
    if problems:
        raise HTTPException(422, {"message": "Documentación insuficiente", "problems": problems})
    previous = case.status
    case.status = CaseStatus.PENDIENTE_REVISION.value
    case.submitted_at = datetime.now(timezone.utc)
    case.status_reason = None
    case_event(db, case.id, "ENVIADO", "Reenviado tras corrección" if previous == CaseStatus.CORRECCION_SOLICITADA.value else "Enviado a revisión", user)
    db.flush()
    auto_assign(db, case, user)
    if previous == CaseStatus.CORRECCION_SOLICITADA.value:
        for a in case.assignments:
            if a.active:
                notify(db, a.reviewer_id, "Expediente corregido", f"{case.code} fue reenviado", f"/revisor/expedientes/{case.id}")
    audit(db, "CASE_SUBMITTED", user, "case", case.id, request)
    db.commit()
    db.expire_all()
    return case_detail(db, case, view="owner")
