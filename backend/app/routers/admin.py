"""Administración técnica: usuarios, asignaciones, categorías, auditoría, conservación y derechos del titular.

La administración NO otorga acceso al contenido de expedientes ni a las evidencias.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..audit import audit, case_event, notify
from ..config import get_settings
from ..db import get_db
from ..deps import require_admin, reviewer_cleared_for
from ..models import (
    AuditLog,
    Case,
    CaseAssignment,
    CaseStatus,
    Category,
    Contribution,
    DataRightsRequest,
    FileStatus,
    PublicationStatus,
    Role,
    Sensitivity,
    StoredFile,
    SystemSetting,
    User,
    UserSession,
)
from ..security import PASSWORD_RULES, hash_password, iso, make_alias, password_is_strong, utc
from ..serializers import category_out, user_out
from ..services import pipeline, storage
from ..services.antivirus import get_scanner
from ..services.forms import parse_schema
from ..services.policies import floor_for_slug, higher, level

router = APIRouter(prefix="/api/admin", tags=["administración"])

DEFAULT_SETTINGS = {
    "retention_days_rejected": 90,
    "retention_days_closed": 365,
    "retention_days_blocked_files": 30,
}


def get_setting(db: Session, key: str):
    row = db.get(SystemSetting, key)
    return row.value if row else DEFAULT_SETTINGS[key]


@router.get("/overview")
def overview(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    s = get_settings()
    scanner = get_scanner()
    by_status = dict(db.execute(select(Case.status, func.count(Case.id)).group_by(Case.status)).all())
    files = dict(db.execute(select(StoredFile.status, func.count(StoredFile.id)).group_by(StoredFile.status)).all())
    roles = dict(db.execute(select(User.role, func.count(User.id)).group_by(User.role)).all())
    assigned_ids = select(CaseAssignment.case_id).where(CaseAssignment.active.is_(True))
    unassigned = db.scalar(
        select(func.count(Case.id)).where(Case.status.in_([CaseStatus.PENDIENTE_REVISION.value, CaseStatus.APROBADO.value]), Case.id.not_in(assigned_ids))
    )
    pending_rights = db.scalar(select(func.count(DataRightsRequest.id)).where(DataRightsRequest.status == "PENDIENTE"))
    return {
        "cases_by_status": by_status,
        "files_by_status": files,
        "users_by_role": roles,
        "unassigned_cases": unassigned,
        "pending_rights_requests": pending_rights,
        "system": {
            "antivirus_engine": scanner.name,
            "antivirus_available": scanner.available(),
            "ffmpeg": s.resolved_ffmpeg() is not None,
            "ffprobe": s.resolved_ffprobe() is not None,
            "demo_mode": s.demo_mode,
            "env": s.env,
        },
    }


# ---------------------------------------------------------------- usuarios
class StaffIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=10, max_length=128)
    role: Literal["REVISOR", "ADMIN"]
    can_review_restricted: bool = False
    can_review_institutional: bool = False


class UserPatch(BaseModel):
    is_active: bool | None = None
    can_review_restricted: bool | None = None
    can_review_institutional: bool | None = None


@router.get("/users")
def users(role: str | None = Query(default=None, max_length=20), user: User = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(User).order_by(User.role, User.full_name)
    if role:
        stmt = stmt.where(User.role == role)
    out = []
    for u in db.scalars(stmt):
        row = user_out(u)
        if u.role == Role.REVISOR.value:
            row["active_assignments"] = db.scalar(select(func.count(CaseAssignment.id)).where(CaseAssignment.reviewer_id == u.id, CaseAssignment.active.is_(True)))
        out.append(row)
    return out


@router.post("/users", status_code=201)
def create_staff(body: StaffIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if not password_is_strong(body.password):
        raise HTTPException(422, PASSWORD_RULES)
    if db.scalar(select(User.id).where(User.email == body.email.lower())):
        raise HTTPException(409, "Ya existe una cuenta con ese correo")
    if body.role == "ADMIN" and (body.can_review_restricted or body.can_review_institutional):
        raise HTTPException(422, "Los administradores no reciben permisos de examen de evidencias")
    u = User(email=body.email.lower(), full_name=body.full_name.strip(), password_hash=hash_password(body.password), role=body.role, alias="tmp",
             can_review_restricted=body.can_review_restricted, can_review_institutional=body.can_review_institutional)
    db.add(u)
    db.flush()
    u.alias = make_alias(u.id)
    audit(db, "STAFF_CREATED", user, "user", u.id, request, role=u.role)
    db.commit()
    return user_out(u)


@router.patch("/users/{uid}")
def patch_user(uid: int, body: UserPatch, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, uid)
    if not u:
        raise HTTPException(404, "Usuario no encontrado")
    data = body.model_dump(exclude_unset=True)
    if u.id == user.id and data.get("is_active") is False:
        raise HTTPException(409, "No puede desactivar su propia cuenta")
    if u.role != Role.REVISOR.value and (data.get("can_review_restricted") or data.get("can_review_institutional")):
        raise HTTPException(422, "Solo los revisores pueden recibir permisos de examen de evidencias sensibles")
    for k, v in data.items():
        setattr(u, k, v)
    if data.get("is_active") is False:
        db.execute(delete(UserSession).where(UserSession.user_id == u.id))
    audit(db, "USER_UPDATED", user, "user", u.id, request, changes=data)
    db.commit()
    return user_out(u)


# ---------------------------------------------------------------- expedientes (solo metadatos)
@router.get("/cases")
def admin_cases(status: str | None = Query(default=None, max_length=40), user: User = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(Case).where(Case.status != CaseStatus.BORRADOR.value).order_by(Case.created_at.desc())
    if status:
        stmt = stmt.where(Case.status == status)
    out = []
    for c in db.scalars(stmt):
        out.append({
            "id": c.id,
            "code": c.code,
            "category": c.category.name,
            "sensitivity": c.sensitivity,
            "status": c.status,
            "publication_status": c.publication_status,
            "created_at": iso(c.created_at),
            "assigned": [{"id": a.reviewer_id, "full_name": a.reviewer.full_name} for a in c.assignments if a.active],
        })
    return out


class AssignIn(BaseModel):
    reviewer_id: int


@router.post("/cases/{case_id}/assignments", status_code=201)
def assign(case_id: int, body: AssignIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    case = db.get(Case, case_id)
    if not case:
        raise HTTPException(404, "Expediente no encontrado")
    rev = db.get(User, body.reviewer_id)
    if not rev or rev.role != Role.REVISOR.value or not rev.is_active:
        raise HTTPException(422, "El usuario indicado no es un revisor activo")
    if not reviewer_cleared_for(rev, case.sensitivity):
        raise HTTPException(422, f"El revisor no tiene habilitación para expedientes {case.sensitivity}")
    existing = db.scalar(select(CaseAssignment).where(CaseAssignment.case_id == case.id, CaseAssignment.reviewer_id == rev.id))
    if existing:
        existing.active = True
        existing.assigned_by = user.id
    else:
        db.add(CaseAssignment(case_id=case.id, reviewer_id=rev.id, assigned_by=user.id))
    case_event(db, case.id, "ASIGNADO", f"Asignado a {rev.full_name} por administración", user, visible_to_reporter=False)
    notify(db, rev.id, "Nuevo expediente asignado", f"{case.code}", f"/revisor/expedientes/{case.id}")
    audit(db, "CASE_ASSIGNED", user, "case", case.id, request, reviewer_id=rev.id)
    db.commit()
    return {"ok": True}


@router.delete("/cases/{case_id}/assignments/{reviewer_id}")
def unassign(case_id: int, reviewer_id: int, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    a = db.scalar(select(CaseAssignment).where(CaseAssignment.case_id == case_id, CaseAssignment.reviewer_id == reviewer_id, CaseAssignment.active.is_(True)))
    if not a:
        raise HTTPException(404, "Asignación no encontrada")
    a.active = False
    case_event(db, case_id, "DESASIGNADO", f"Se retiró la asignación de {a.reviewer.full_name}", user, visible_to_reporter=False)
    audit(db, "CASE_UNASSIGNED", user, "case", case_id, request, reviewer_id=reviewer_id)
    db.commit()
    return {"ok": True}


# ---------------------------------------------------------------- categorías
@router.get("/categories")
def admin_categories(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    cats = db.scalars(select(Category).where(Category.parent_id.is_(None)).order_by(Category.sort_order)).all()
    out = []
    for c in cats:
        row = category_out(c, with_children=False)
        row["children"] = [category_out(ch, False) for ch in sorted(c.children, key=lambda x: x.sort_order)]
        out.append(row)
    return out


class CategoryPatch(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    sensitivity: Sensitivity | None = None
    active: bool | None = None
    field_schema: list[dict] | None = None
    document_policy: dict | None = None


class CategoryIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]{3,80}$")
    name: str = Field(min_length=3, max_length=120)
    description: str = Field(default="", max_length=500)
    icon: str = Field(default="circle-help", pattern=r"^[a-z0-9-]{2,40}$")
    parent_id: int | None = None
    sensitivity: Sensitivity = Sensitivity.GENERAL
    field_schema: list[dict] = Field(default_factory=list)
    document_policy: dict = Field(default_factory=lambda: {"min_documents": 1})


def _validate_policy(p: dict) -> dict:
    from .public import DOC_TYPES

    md = p.get("min_documents", 1)
    if not isinstance(md, int) or not 0 <= md <= 10:
        raise HTTPException(422, "min_documents debe ser un entero entre 0 y 10")
    groups = p.get("required_any", [])
    if not isinstance(groups, list) or any(not isinstance(g, list) or any(t not in DOC_TYPES for t in g) for g in groups):
        raise HTTPException(422, "required_any debe ser una lista de grupos de tipos de documento válidos")
    return {"min_documents": md, "required_any": groups, "note": str(p.get("note", ""))[:300]}


def _validate_schema(raw: list[dict]) -> list[dict]:
    try:
        return [f.model_dump(exclude_none=True) for f in parse_schema(raw)]
    except Exception as e:  # noqa: BLE001
        raise HTTPException(422, f"Esquema de campos inválido: {e}") from None


@router.post("/categories", status_code=201)
def create_category(body: CategoryIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    if db.scalar(select(Category.id).where(Category.slug == body.slug)):
        raise HTTPException(409, "Ya existe una categoría con ese identificador")
    if body.parent_id and not db.get(Category, body.parent_id):
        raise HTTPException(422, "Categoría padre no válida")
    floor = floor_for_slug(body.slug)
    cat = Category(slug=body.slug, name=body.name, description=body.description, icon=body.icon, parent_id=body.parent_id,
                   sensitivity=higher(body.sensitivity.value, floor), min_sensitivity=floor,
                   field_schema=_validate_schema(body.field_schema), document_policy=_validate_policy(body.document_policy), sort_order=100)
    db.add(cat)
    db.flush()
    audit(db, "CATEGORY_CREATED", user, "category", cat.id, request, slug=cat.slug)
    db.commit()
    return category_out(cat)


@router.patch("/categories/{cat_id}")
def patch_category(cat_id: int, body: CategoryPatch, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    cat = db.get(Category, cat_id)
    if not cat:
        raise HTTPException(404, "Categoría no encontrada")
    data = body.model_dump(exclude_unset=True)
    if "sensitivity" in data and data["sensitivity"] is not None:
        requested = data["sensitivity"].value
        floor = higher(cat.min_sensitivity, floor_for_slug(cat.slug))
        if level(requested) < level(floor):
            raise HTTPException(422, f"Protección reforzada: esta categoría no puede tener una sensibilidad inferior a {floor}")
        data["sensitivity"] = requested
    if "field_schema" in data and data["field_schema"] is not None:
        data["field_schema"] = _validate_schema(data["field_schema"])
    if "document_policy" in data and data["document_policy"] is not None:
        data["document_policy"] = _validate_policy(data["document_policy"])
    for k, v in data.items():
        setattr(cat, k, v)
    db.flush()
    upgraded = 0
    if "sensitivity" in data:
        # Elevar (nunca reducir) la sensibilidad de expedientes existentes de la categoría y subcategorías
        cat_ids = [cat.id] + [c.id for c in cat.children]
        for case in db.scalars(select(Case).where(Case.category_id.in_(cat_ids))):
            new = higher(case.sensitivity, data["sensitivity"])
            if new != case.sensitivity:
                case.sensitivity = new
                upgraded += 1
                if new == Sensitivity.INSTITUCIONAL.value:
                    case.contributions_open = False
                    if case.publication_status in (PublicationStatus.PUBLICADO.value, PublicationStatus.PENDIENTE_SEGUNDA_APROBACION.value):
                        case.publication_status = PublicationStatus.RETIRADO.value
                        if case.public_card:
                            case.public_card.withdrawn_at = datetime.now(timezone.utc)
                case_event(db, case.id, "SENSIBILIDAD", f"Sensibilidad elevada a {new} por cambio de política de categoría", user, visible_to_reporter=False)
    audit(db, "CATEGORY_UPDATED", user, "category", cat.id, request, fields=sorted(data.keys()), upgraded_cases=upgraded)
    db.commit()
    return category_out(cat) | {"upgraded_cases": upgraded}


# ---------------------------------------------------------------- auditoría
@router.get("/audit")
def audit_log(
    action: str | None = Query(default=None, max_length=60),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    stmt = select(AuditLog).order_by(AuditLog.at.desc(), AuditLog.id.desc())
    if action:
        stmt = stmt.where(AuditLog.action == action)
    rows = db.scalars(stmt.offset(offset).limit(limit)).all()
    return [
        {"id": r.id, "at": iso(r.at), "action": r.action, "actor": r.actor.full_name if r.actor else "Sistema", "actor_role": r.actor.role if r.actor else None,
         "entity_type": r.entity_type, "entity_id": r.entity_id, "ip": r.ip, "details": r.details}
        for r in rows
    ]


# ---------------------------------------------------------------- configuración y conservación
class SettingsIn(BaseModel):
    retention_days_rejected: int | None = Field(default=None, ge=7, le=3650)
    retention_days_closed: int | None = Field(default=None, ge=30, le=3650)
    retention_days_blocked_files: int | None = Field(default=None, ge=1, le=365)


@router.get("/settings")
def read_settings(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return {k: get_setting(db, k) for k in DEFAULT_SETTINGS}


@router.put("/settings")
def write_settings(body: SettingsIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    for k, v in body.model_dump(exclude_none=True).items():
        row = db.get(SystemSetting, k)
        if row:
            row.value = v
            row.updated_by = user.id
        else:
            db.add(SystemSetting(key=k, value=v, updated_by=user.id))
    audit(db, "SETTINGS_UPDATED", user, "settings", None, request, **body.model_dump(exclude_none=True))
    db.commit()
    return {k: get_setting(db, k) for k in DEFAULT_SETTINGS}


class RetentionIn(BaseModel):
    dry_run: bool = True


def _purge_case(db: Session, case: Case) -> int:
    n = 0
    for sf in db.scalars(select(StoredFile).where(StoredFile.case_id == case.id, StoredFile.status != FileStatus.ELIMINADO.value)):
        storage.delete_physical(sf.internal_name, sf.playback_name)
        sf.status = FileStatus.ELIMINADO.value
        sf.status_detail = "Eliminado por política de conservación"
        sf.playback_name = None
        n += 1
    case.description = "[Contenido eliminado por política de conservación]"
    case.specific_fields = {}
    case.private_lat = case.private_lon = None
    case.private_location_note = None
    for c in db.scalars(select(Contribution).where(Contribution.case_id == case.id)):
        c.description = "[Contenido eliminado por política de conservación]"
        c.declared_lat = c.declared_lon = None
        c.location_note = None
    case_event(db, case.id, "CONSERVACION", "Datos y archivos eliminados por política de conservación", None)
    return n


@router.post("/retention/run")
def run_retention(body: RetentionIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    now = datetime.now(timezone.utc)
    rej_days = get_setting(db, "retention_days_rejected")
    closed_days = get_setting(db, "retention_days_closed")
    blocked_days = get_setting(db, "retention_days_blocked_files")
    candidates = []
    for case in db.scalars(select(Case).where(Case.status.in_([CaseStatus.RECHAZADO.value, CaseStatus.CERRADO.value]))):
        limit_days = rej_days if case.status == CaseStatus.RECHAZADO.value else closed_days
        decided = utc(case.decided_at or case.updated_at)
        if decided and decided < now - timedelta(days=limit_days) and not case.description.startswith("[Contenido eliminado"):
            candidates.append(case)
    bad_files = [
        sf for sf in db.scalars(select(StoredFile).where(StoredFile.status.in_([
            FileStatus.BLOQUEADO_SIN_ANTIVIRUS.value, FileStatus.INFECTADO.value, FileStatus.RECHAZADO_FORMATO.value, FileStatus.ERROR_PROCESAMIENTO.value])))
        if utc(sf.uploaded_at) < now - timedelta(days=blocked_days)
    ]
    result = {"dry_run": body.dry_run, "cases": [c.code for c in candidates], "blocked_files": len(bad_files), "files_deleted": 0}
    if not body.dry_run:
        for c in candidates:
            result["files_deleted"] += _purge_case(db, c)
        for sf in bad_files:
            storage.delete_physical(sf.internal_name, sf.playback_name)
            sf.status = FileStatus.ELIMINADO.value
            sf.status_detail = "Eliminado por política de conservación (archivo no validado)"
            result["files_deleted"] += 1
    audit(db, "RETENTION_RUN", user, "settings", None, request, **{k: v for k, v in result.items() if k != "cases"}, cases=len(candidates))
    db.commit()
    return result


# ---------------------------------------------------------------- derechos del titular
@router.get("/data-requests")
def rights_requests(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [
        {"id": r.id, "user": {"id": r.user_id, "full_name": r.user.full_name, "email": r.user.email}, "rtype": r.rtype, "detail": r.detail,
         "status": r.status, "response": r.response, "created_at": iso(r.created_at), "resolved_at": iso(r.resolved_at)}
        for r in db.scalars(select(DataRightsRequest).order_by(DataRightsRequest.created_at.desc()))
    ]


class ResolveIn(BaseModel):
    status: Literal["ATENDIDA", "DENEGADA"]
    response: str = Field(min_length=10, max_length=2000)
    anonymize_account: bool = False


@router.post("/data-requests/{rid}/resolve")
def resolve_rights(rid: int, body: ResolveIn, request: Request, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    r = db.get(DataRightsRequest, rid)
    if not r:
        raise HTTPException(404, "Solicitud no encontrada")
    if r.status != "PENDIENTE":
        raise HTTPException(409, "La solicitud ya fue resuelta")
    if body.anonymize_account:
        if r.rtype not in ("CANCELACION", "OPOSICION") or body.status != "ATENDIDA":
            raise HTTPException(422, "La anonimización solo procede al atender una solicitud de cancelación u oposición")
        u = r.user
        if u.role in (Role.ADMIN.value, Role.REVISOR.value):
            raise HTTPException(422, "Las cuentas del personal se gestionan por baja administrativa")
        u.email = f"anonimizado-{u.id}@anonimizado.invalid"
        u.full_name = "Titular anonimizado"
        u.is_active = False
        u.anonymized_at = datetime.now(timezone.utc)
        db.execute(delete(UserSession).where(UserSession.user_id == u.id))
    r.status = body.status
    r.response = body.response.strip()
    r.resolved_by = user.id
    r.resolved_at = datetime.now(timezone.utc)
    if r.user.is_active:
        notify(db, r.user_id, "Su solicitud de derechos fue atendida", body.response.strip()[:200], "/cuenta")
    audit(db, "DATA_RIGHTS_RESOLVED", user, "data_request", r.id, request, status=body.status, anonymized=body.anonymize_account)
    db.commit()
    return {"id": r.id, "status": r.status}


@router.post("/files/{file_id}/rescan")
def rescan(file_id: str, request: Request, background: BackgroundTasks, user: User = Depends(require_admin), db: Session = Depends(get_db)):
    sf = db.get(StoredFile, file_id)
    if not sf:
        raise HTTPException(404, "Archivo no encontrado")
    # Un archivo que sigue en cuarentena más de 10 min indica que el procesamiento se interrumpió (p. ej. reinicio)
    stale_quarantine = sf.status == FileStatus.CUARENTENA.value and utc(sf.uploaded_at) < datetime.now(timezone.utc) - timedelta(minutes=10)
    if sf.status not in (FileStatus.BLOQUEADO_SIN_ANTIVIRUS.value, FileStatus.ERROR_PROCESAMIENTO.value) and not stale_quarantine:
        raise HTTPException(409, "Solo se reanalizan archivos bloqueados, con error o detenidos en cuarentena")
    audit(db, "FILE_RESCAN", user, "file", sf.id, request)
    db.commit()
    pipeline.schedule_processing(background, sf.id)
    return {"ok": True}


@router.get("/files/blocked")
def blocked_files(user: User = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(StoredFile).where(StoredFile.status.in_([FileStatus.BLOQUEADO_SIN_ANTIVIRUS.value, FileStatus.ERROR_PROCESAMIENTO.value, FileStatus.CUARENTENA.value]))).all()
    # Solo metadatos técnicos; sin nombre original ni contenido
    return [{"id": f.id, "status": f.status, "status_detail": f.status_detail, "size_bytes": f.size_bytes, "detected_type": f.detected_type,
             "uploaded_at": iso(f.uploaded_at)} for f in rows]
