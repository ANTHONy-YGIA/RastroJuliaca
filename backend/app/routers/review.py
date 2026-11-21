"""Panel del revisor: revisión documental, publicación moderada, evidencias, filtros y línea de tiempo.

Todas las rutas verifican asignación y habilitación del revisor (protección IDOR).
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..audit import audit, case_event, notify
from ..db import get_db
from ..deps import get_case_for_reviewer, require_reviewer, reviewer_cleared_for
from ..models import (
    Case,
    CaseAssignment,
    CaseDecision,
    CaseEvent,
    CaseStatus,
    Category,
    Classification,
    Contribution,
    ContributionStatus,
    DocReviewStatus,
    FileStatus,
    Observation,
    PublicCard,
    PublicationStatus,
    Report,
    Sensitivity,
    SupportingDocument,
    User,
)
from ..security import PERU_TZ, iso, utc
from ..serializers import case_detail, case_summary, category_effective, contribution_out, corrections_for, effective_values
from ..services.geo import distance_or_none, hours_between
from ..services.policies import can_open_contributions, can_publish
from .contributions import CorrectionIn, apply_correction

router = APIRouter(prefix="/api/review", tags=["revisión"])


def _assigned_case_ids(db: Session, user: User) -> list[int]:
    rows = db.execute(
        select(Case.id, Case.sensitivity)
        .join(CaseAssignment, CaseAssignment.case_id == Case.id)
        .where(CaseAssignment.reviewer_id == user.id, CaseAssignment.active.is_(True))
    ).all()
    return [cid for cid, sens in rows if reviewer_cleared_for(user, sens)]


@router.get("/dashboard")
def dashboard(user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    ids = _assigned_case_ids(db, user)

    def count_cases(*statuses: str) -> int:
        if not ids:
            return 0
        return db.scalar(select(func.count(Case.id)).where(Case.id.in_(ids), Case.status.in_(statuses))) or 0

    def count_contrib(*statuses: str) -> int:
        if not ids:
            return 0
        return db.scalar(select(func.count(Contribution.id)).where(Contribution.case_id.in_(ids), Contribution.status.in_(statuses))) or 0

    recent = []
    if ids:
        events = db.scalars(
            select(CaseEvent)
            .where(CaseEvent.case_id.in_(ids), CaseEvent.event.in_(["DECISION", "CLASIFICACION", "PUBLICACION", "INFORME", "APORTACION_VALIDADA", "ENVIADO"]))
            .order_by(CaseEvent.created_at.desc(), CaseEvent.id.desc())
            .limit(12)
        ).all()
        codes = dict(db.execute(select(Case.id, Case.code).where(Case.id.in_({e.case_id for e in events}))).all()) if events else {}
        recent = [
            {"case_id": e.case_id, "case_code": codes.get(e.case_id), "event": e.event, "detail": e.detail, "created_at": iso(e.created_at),
             "actor": e.actor.full_name if e.actor else "Sistema"}
            for e in events
        ]
    pending_contribs = []
    if ids:
        for c in db.scalars(
            select(Contribution).where(Contribution.case_id.in_(ids), Contribution.status == ContributionStatus.PENDIENTE_REVISION.value).order_by(Contribution.created_at).limit(8)
        ):
            pending_contribs.append({"id": c.id, "code": c.code, "case_code": c.case.code, "type": c.ctype, "created_at": iso(c.created_at)})
    return {
        "counts": {
            "assigned": len(ids),
            "cases_pending": count_cases(CaseStatus.PENDIENTE_REVISION.value),
            "cases_correction": count_cases(CaseStatus.CORRECCION_SOLICITADA.value),
            "cases_approved": count_cases(CaseStatus.APROBADO.value),
            "cases_rejected": count_cases(CaseStatus.RECHAZADO.value),
            "evidence_pending": count_contrib(ContributionStatus.PENDIENTE_REVISION.value),
            "evidence_validating": count_contrib(ContributionStatus.EN_VALIDACION.value, ContributionStatus.BLOQUEADA.value),
            "evidence_classified": count_contrib(ContributionStatus.CLASIFICADA.value),
            "reports": db.scalar(select(func.count(Report.id)).where(Report.case_id.in_(ids))) if ids else 0,
            "publication_pending": db.scalar(
                select(func.count(Case.id)).where(Case.id.in_(ids), Case.publication_status == PublicationStatus.PENDIENTE_SEGUNDA_APROBACION.value)
            ) if ids else 0,
        },
        "recent": recent,
        "pending_contributions": pending_contribs,
        "clearance": {"restricted": user.can_review_restricted or user.can_review_institutional, "institutional": user.can_review_institutional},
    }


@router.get("/cases")
def review_cases(
    status: str | None = Query(default=None, max_length=40),
    category: str | None = Query(default=None, max_length=80),
    sensitivity: str | None = Query(default=None, max_length=20),
    q: str | None = Query(default=None, max_length=100),
    sort: Literal["received", "incident", "category", "status"] = "received",
    user: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    ids = _assigned_case_ids(db, user)
    if not ids:
        return []
    stmt = select(Case).where(Case.id.in_(ids), Case.status != CaseStatus.BORRADOR.value)
    if status:
        stmt = stmt.where(Case.status == status)
    if sensitivity:
        stmt = stmt.where(Case.sensitivity == sensitivity)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Case.code.ilike(like), Case.title.ilike(like), Case.description.ilike(like)))
    cases = db.scalars(stmt).all()
    if category:
        cases = [c for c in cases if c.category.slug == category or (c.category.parent and c.category.parent.slug == category)]
    keyf = {
        "received": lambda c: utc(c.submitted_at or c.created_at),
        "incident": lambda c: utc(c.incident_at),
        "category": lambda c: (c.category.parent.name if c.category.parent else c.category.name, c.category.name),
        "status": lambda c: c.status,
    }[sort]
    cases = sorted(cases, key=keyf, reverse=sort in ("received", "incident"))
    out = []
    for c in cases:
        row = case_summary(c)
        row["pending_contributions"] = db.scalar(
            select(func.count(Contribution.id)).where(Contribution.case_id == c.id, Contribution.status == ContributionStatus.PENDIENTE_REVISION.value)
        )
        out.append(row)
    return out


@router.get("/cases/{case_id}")
def review_case(case_id: int, request: Request, user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    case = get_case_for_reviewer(db, case_id, user)
    audit(db, "CASE_VIEWED", user, "case", case.id, request)
    db.commit()
    return case_detail(db, case, view="reviewer")


class DecisionIn(BaseModel):
    decision: Literal["APROBAR", "RECHAZAR", "SOLICITAR_CORRECCION", "CERRAR"]
    reason: str = Field(min_length=5, max_length=2000)


@router.post("/cases/{case_id}/decision")
def decide(case_id: int, body: DecisionIn, request: Request, user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    case = get_case_for_reviewer(db, case_id, user)
    d = body.decision
    if d in ("APROBAR", "RECHAZAR", "SOLICITAR_CORRECCION") and case.status != CaseStatus.PENDIENTE_REVISION.value:
        raise HTTPException(409, "Solo se decide sobre expedientes pendientes de revisión")
    if d == "CERRAR" and case.status != CaseStatus.APROBADO.value:
        raise HTTPException(409, "Solo se cierran expedientes aprobados")
    if d == "APROBAR":
        accepted = [doc for doc in case.documents if doc.review_status == DocReviewStatus.ACEPTADO.value]
        if not accepted:
            raise HTTPException(422, "Debe examinar y aceptar al menos un documento de respaldo antes de aprobar")
    new_status = {
        "APROBAR": CaseStatus.APROBADO,
        "RECHAZAR": CaseStatus.RECHAZADO,
        "SOLICITAR_CORRECCION": CaseStatus.CORRECCION_SOLICITADA,
        "CERRAR": CaseStatus.CERRADO,
    }[d].value
    case.status = new_status
    case.status_reason = body.reason.strip()
    case.decided_at = datetime.now(timezone.utc)
    if d in ("RECHAZAR", "CERRAR"):
        case.contributions_open = False
        if case.public_card and case.publication_status == PublicationStatus.PUBLICADO.value:
            case.publication_status = PublicationStatus.RETIRADO.value
            case.public_card.withdrawn_at = datetime.now(timezone.utc)
    db.add(CaseDecision(case_id=case.id, reviewer_id=user.id, decision=d, reason=body.reason.strip()))
    labels = {"APROBAR": "Aprobado", "RECHAZAR": "Rechazado", "SOLICITAR_CORRECCION": "Corrección solicitada", "CERRAR": "Cerrado"}
    case_event(db, case.id, "DECISION", f"{labels[d]}: {body.reason.strip()}", user)
    notify(db, case.reporter_id, f"Su expediente {case.code}: {labels[d]}", body.reason.strip(), f"/mis-expedientes/{case.id}")
    audit(db, "CASE_DECISION", user, "case", case.id, request, decision=d)
    db.commit()
    db.expire_all()
    return case_detail(db, db.get(Case, case.id), view="reviewer")


class DocAssessmentIn(BaseModel):
    status: Literal["ACEPTADO", "OBSERVADO"]
    note: str = Field(default="", max_length=1000)


@router.post("/documents/{doc_id}/assessment")
def assess_document(doc_id: int, body: DocAssessmentIn, request: Request, user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    doc = db.get(SupportingDocument, doc_id)
    if not doc:
        raise HTTPException(404, "Documento no encontrado")
    case = get_case_for_reviewer(db, doc.case_id, user)
    if body.status == "ACEPTADO" and doc.file.status != FileStatus.DISPONIBLE.value:
        raise HTTPException(409, "El documento aún no superó la validación de seguridad y no pudo examinarse")
    if body.status == "OBSERVADO" and len(body.note.strip()) < 5:
        raise HTTPException(422, "Indique el motivo de la observación")
    doc.review_status = body.status
    doc.review_note = body.note.strip() or None
    case_event(db, case.id, "DOCUMENTO_REVISADO", f"Documento #{doc.id}: {body.status}" + (f" — {body.note.strip()}" if body.note.strip() else ""), user)
    audit(db, "DOCUMENT_ASSESSED", user, "document", doc.id, request, status=body.status)
    db.commit()
    return {"id": doc.id, "review_status": doc.review_status, "review_note": doc.review_note}


class PublicationIn(BaseModel):
    public_title: str = Field(min_length=5, max_length=160)
    public_summary: str = Field(min_length=20, max_length=1500)
    public_field_keys: list[str] = Field(default_factory=list)


PII_PATTERNS = [
    (re.compile(r"\b\d{8}\b"), "posible número de DNI"),
    (re.compile(r"\b9\d{8}\b"), "posible número telefónico"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"), "correo electrónico"),
    (re.compile(r"-?\d{1,2}\.\d{4,}\s*,\s*-?\d{1,3}\.\d{4,}"), "coordenadas exactas"),
]


def _minimization_problems(case: Case, text: str) -> list[str]:
    problems = [label for rx, label in PII_PATTERNS if rx.search(text)]
    low = text.lower()
    if case.reporter.full_name.lower() in low:
        problems.append("nombre del denunciante")
    if case.private_location_note and case.private_location_note.lower() in low:
        problems.append("ubicación privada")
    return problems


@router.post("/cases/{case_id}/publication")
def request_publication(case_id: int, body: PublicationIn, request: Request, user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    case = get_case_for_reviewer(db, case_id, user)
    ok, reason = can_publish(case)
    if not ok:
        raise HTTPException(409, reason)
    problems = _minimization_problems(case, f"{body.public_title}\n{body.public_summary}")
    if problems:
        raise HTTPException(422, {"message": "La ficha pública contiene datos que deben minimizarse", "problems": problems})
    schema, _ = category_effective(case.category)
    publicable = {f["key"] for f in schema if f.get("public")}
    keys = list(dict.fromkeys(body.public_field_keys))
    if case.sensitivity == Sensitivity.RESTRINGIDO.value and keys:
        raise HTTPException(422, "Los expedientes RESTRINGIDOS no pueden publicar campos específicos")
    bad = [k for k in keys if k not in publicable]
    if bad:
        raise HTTPException(422, f"Campos no publicables: {', '.join(bad)}")
    labels = {f["key"]: f["label"] for f in schema}
    public_fields = {labels[k]: case.specific_fields[k] for k in keys if k in (case.specific_fields or {})}
    incident_date = utc(case.incident_at).astimezone(PERU_TZ).date().isoformat()
    now = datetime.now(timezone.utc)
    pc = case.public_card or PublicCard(case_id=case.id, requested_by=user.id, public_title="", public_summary="", zone=case.zone, incident_date=incident_date)
    pc.public_title = body.public_title.strip()
    pc.public_summary = body.public_summary.strip()
    pc.zone = case.zone
    pc.incident_date = incident_date
    pc.public_fields = public_fields
    pc.requested_by = user.id
    pc.approved_by = None
    pc.withdrawn_at = None
    if case.public_card is None:
        db.add(pc)
    if case.sensitivity == Sensitivity.RESTRINGIDO.value:
        case.publication_status = PublicationStatus.PENDIENTE_SEGUNDA_APROBACION.value
        pc.published_at = None
        case_event(db, case.id, "PUBLICACION", "Publicación solicitada: requiere segunda aprobación (revisión reforzada)", user)
        for a in case.assignments:
            if a.active and a.reviewer_id != user.id:
                notify(db, a.reviewer_id, "Segunda aprobación requerida", f"{case.code}: confirmar ficha pública", f"/revisor/expedientes/{case.id}")
    else:
        case.publication_status = PublicationStatus.PUBLICADO.value
        pc.approved_by = user.id
        pc.published_at = now
        case_event(db, case.id, "PUBLICACION", "Ficha pública generalizada publicada", user)
        notify(db, case.reporter_id, f"{case.code}: ficha pública publicada", "Se publicó una ficha generalizada sin datos privados.", f"/mis-expedientes/{case.id}")
    audit(db, "PUBLICATION_REQUESTED", user, "case", case.id, request, fields=keys, status=case.publication_status)
    db.commit()
    db.expire_all()
    return case_detail(db, db.get(Case, case.id), view="reviewer")


@router.post("/cases/{case_id}/publication/confirm")
def confirm_publication(case_id: int, request: Request, user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    case = get_case_for_reviewer(db, case_id, user)
    if case.publication_status != PublicationStatus.PENDIENTE_SEGUNDA_APROBACION.value or not case.public_card:
        raise HTTPException(409, "No hay una publicación pendiente de segunda aprobación")
    if case.public_card.requested_by == user.id:
        raise HTTPException(409, "La segunda aprobación debe realizarla un revisor distinto")
    case.publication_status = PublicationStatus.PUBLICADO.value
    case.public_card.approved_by = user.id
    case.public_card.published_at = datetime.now(timezone.utc)
    case_event(db, case.id, "PUBLICACION", "Segunda aprobación registrada: ficha mínima publicada", user)
    notify(db, case.reporter_id, f"{case.code}: ficha pública publicada", "Se publicó una ficha mínima tras revisión reforzada.", f"/mis-expedientes/{case.id}")
    audit(db, "PUBLICATION_CONFIRMED", user, "case", case.id, request)
    db.commit()
    db.expire_all()
    return case_detail(db, db.get(Case, case.id), view="reviewer")


class ReasonIn(BaseModel):
    reason: str = Field(min_length=5, max_length=1000)


@router.post("/cases/{case_id}/publication/withdraw")
def withdraw_publication(case_id: int, body: ReasonIn, request: Request, user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    case = get_case_for_reviewer(db, case_id, user)
    if case.publication_status not in (PublicationStatus.PUBLICADO.value, PublicationStatus.PENDIENTE_SEGUNDA_APROBACION.value):
        raise HTTPException(409, "No hay publicación vigente")
    case.publication_status = PublicationStatus.RETIRADO.value
    case.contributions_open = False
    if case.public_card:
        case.public_card.withdrawn_at = datetime.now(timezone.utc)
    case_event(db, case.id, "PUBLICACION", f"Ficha pública retirada: {body.reason.strip()}", user)
    audit(db, "PUBLICATION_WITHDRAWN", user, "case", case.id, request)
    db.commit()
    db.expire_all()
    return case_detail(db, db.get(Case, case.id), view="reviewer")


class OpenIn(BaseModel):
    open: bool


@router.post("/cases/{case_id}/contributions-open")
def set_contributions_open(case_id: int, body: OpenIn, request: Request, user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    case = get_case_for_reviewer(db, case_id, user)
    if body.open:
        ok, reason = can_open_contributions(case)
        if not ok:
            raise HTTPException(409, reason)
    case.contributions_open = body.open
    case_event(db, case.id, "APORTACIONES", "Aportaciones habilitadas" if body.open else "Aportaciones cerradas", user)
    audit(db, "CONTRIBUTIONS_TOGGLED", user, "case", case.id, request, open=body.open)
    db.commit()
    return {"contributions_open": case.contributions_open}


# ---------------------------------------------------------------- aportaciones
def _enriched(db: Session, case: Case, c: Contribution) -> dict:
    out = contribution_out(db, c, view="reviewer")
    eff = out["effective"]
    when = datetime.fromisoformat(eff["declared_at"].replace("Z", "+00:00")) if eff["declared_at"] else None
    dist = distance_or_none(case.private_lat, case.private_lon, eff["declared_lat"], eff["declared_lon"])
    dt_h = hours_between(utc(case.incident_at), when)
    out["distance_km"] = dist
    out["time_diff_h"] = dt_h
    notes = []
    if dist is None:
        notes.append("Datos de ubicación insuficientes" + ("" if case.private_lat is not None else " (el expediente no tiene ubicación privada)"))
    if dt_h is None:
        notes.append("Fecha u hora declarada insuficiente")
    out["data_quality"] = notes
    return out


@router.get("/cases/{case_id}/contributions")
def case_contributions(
    case_id: int,
    sort: Literal["distance", "time", "received", "status"] = "received",
    status: str | None = Query(default=None, max_length=30),
    ctype: str | None = Query(default=None, max_length=20),
    classification: str | None = Query(default=None, max_length=30),
    max_km: float | None = Query(default=None, gt=0, le=500),
    max_hours: float | None = Query(default=None, gt=0, le=24 * 365),
    user: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    case = get_case_for_reviewer(db, case_id, user)
    stmt = select(Contribution).where(Contribution.case_id == case.id)  # aislamiento: solo este expediente
    if status:
        stmt = stmt.where(Contribution.status == status)
    if ctype:
        stmt = stmt.where(Contribution.ctype == ctype)
    if classification:
        stmt = stmt.where(Contribution.classification == classification)
    items = [_enriched(db, case, c) for c in db.scalars(stmt)]
    hidden = 0
    if max_km is not None or max_hours is not None:
        kept = []
        for it in items:
            # Nunca se descartan aportaciones por falta de datos: solo si el dato existe y excede el umbral elegido
            out_km = max_km is not None and it["distance_km"] is not None and it["distance_km"] > max_km
            out_h = max_hours is not None and it["time_diff_h"] is not None and it["time_diff_h"] > max_hours
            if out_km or out_h:
                hidden += 1
            else:
                kept.append(it)
        items = kept
    status_order = {s.value: i for i, s in enumerate(ContributionStatus)}
    big = float("inf")
    if sort == "distance":
        items.sort(key=lambda x: (x["distance_km"] is None, x["distance_km"] if x["distance_km"] is not None else big))
    elif sort == "time":
        items.sort(key=lambda x: (x["time_diff_h"] is None, x["time_diff_h"] if x["time_diff_h"] is not None else big))
    elif sort == "status":
        items.sort(key=lambda x: (status_order.get(x["status"], 99), x["created_at"]))
    else:
        items.sort(key=lambda x: x["created_at"], reverse=True)
    return {
        "case_reference": {
            "has_location": case.private_lat is not None,
            "incident_at": iso(case.incident_at),
        },
        "items": items,
        "hidden_by_filters": hidden,
    }


def _contribution_for_reviewer(db: Session, cid: int, user: User) -> tuple[Case, Contribution]:
    c = db.get(Contribution, cid)
    if not c:
        raise HTTPException(404, "Aportación no encontrada")
    case = get_case_for_reviewer(db, c.case_id, user)
    return case, c


@router.get("/contributions/{cid}")
def review_contribution(cid: int, request: Request, user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    case, c = _contribution_for_reviewer(db, cid, user)
    audit(db, "CONTRIBUTION_VIEWED", user, "contribution", c.id, request)
    db.commit()
    out = _enriched(db, case, c)
    out["case"] = {"id": case.id, "code": case.code, "title": case.title, "incident_at": iso(case.incident_at), "zone": case.zone,
                   "private_lat": case.private_lat, "private_lon": case.private_lon}
    return out


class ClassifyIn(BaseModel):
    classification: Classification
    observation: str = Field(min_length=5, max_length=2000)


@router.post("/contributions/{cid}/classify")
def classify(cid: int, body: ClassifyIn, request: Request, user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    case, c = _contribution_for_reviewer(db, cid, user)
    if c.status not in (ContributionStatus.PENDIENTE_REVISION.value, ContributionStatus.CLASIFICADA.value):
        raise HTTPException(409, "La aportación aún no superó la validación de seguridad")
    previous = c.classification
    c.classification = body.classification.value
    c.status = ContributionStatus.CLASIFICADA.value
    c.classified_by = user.id
    c.classified_at = datetime.now(timezone.utc)
    db.add(Observation(case_id=case.id, contribution_id=c.id, author_id=user.id, text=body.observation.strip()))
    detail = f"{c.code}: {body.classification.value}" + (f" (antes {previous})" if previous else "")
    case_event(db, case.id, "CLASIFICACION", detail, user, visible_to_reporter=False)
    notify(db, c.contributor_id, "Su aportación fue revisada", f"{c.code} fue examinada por el equipo de revisión", "/mis-aportaciones")
    audit(db, "CONTRIBUTION_CLASSIFIED", user, "contribution", c.id, request, classification=body.classification.value, previous=previous)
    db.commit()
    return _enriched(db, case, c)


class ObservationIn(BaseModel):
    text: str = Field(min_length=3, max_length=2000)


@router.post("/contributions/{cid}/observations", status_code=201)
def add_observation(cid: int, body: ObservationIn, request: Request, user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    case, c = _contribution_for_reviewer(db, cid, user)
    db.add(Observation(case_id=case.id, contribution_id=c.id, author_id=user.id, text=body.text.strip()))
    audit(db, "OBSERVATION_ADDED", user, "contribution", c.id, request)
    db.commit()
    return _enriched(db, case, c)


@router.post("/contributions/{cid}/corrections", status_code=201)
def reviewer_correction(cid: int, body: CorrectionIn, request: Request, user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    case, c = _contribution_for_reviewer(db, cid, user)
    apply_correction(db, c, body, user)
    audit(db, "CONTRIBUTION_CORRECTED", user, "contribution", c.id, request, field=body.field)
    db.commit()
    return _enriched(db, case, c)


# ---------------------------------------------------------------- línea de tiempo
@router.get("/cases/{case_id}/timeline")
def timeline(
    case_id: int,
    include_unclassified: bool = True,
    classification: str | None = Query(default=None, max_length=30),
    user: User = Depends(require_reviewer),
    db: Session = Depends(get_db),
):
    case = get_case_for_reviewer(db, case_id, user)
    entries = [
        {
            "kind": "INCIDENTE",
            "at": iso(case.incident_at),
            "label": "Hora del incidente declarada por el denunciante",
            "type": None,
            "description": case.title,
            "status": case.status,
            "classification": None,
            "observations": [],
            "declared": True,
            "corrected": False,
        }
    ]
    undated = []
    for c in db.scalars(select(Contribution).where(Contribution.case_id == case.id)):
        if classification and c.classification != classification:
            continue
        if not include_unclassified and c.status != ContributionStatus.CLASIFICADA.value:
            continue
        corrs = corrections_for(db, c.id)
        eff = effective_values(c, corrs)
        obs = [o.text for o in db.scalars(select(Observation).where(Observation.contribution_id == c.id).order_by(Observation.created_at))]
        item = {
            "kind": "APORTACION",
            "contribution_id": c.id,
            "code": c.code,
            "at": eff["declared_at"],
            "original_at": iso(c.declared_at),
            "label": "Hora declarada por el colaborador (no verificada)",
            "type": c.ctype,
            "description": eff["description"],
            "status": c.status,
            "classification": c.classification,
            "certainty": c.certainty,
            "observations": obs,
            "declared": True,
            "corrected": any(x.field == "declared_at" for x in corrs),
            "corrections": [{"field": x.field, "old_value": x.old_value, "new_value": x.new_value, "reason": x.reason} for x in corrs],
            "distance_km": distance_or_none(case.private_lat, case.private_lon, eff["declared_lat"], eff["declared_lon"]),
        }
        (entries if item["at"] else undated).append(item)
    entries.sort(key=lambda e: e["at"])
    return {
        "case": {"id": case.id, "code": case.code, "title": case.title},
        "notice": "Las fechas y horas son declaradas por los participantes y no constituyen hechos comprobados.",
        "entries": entries,
        "undated": undated,
    }


@router.get("/reviewers")
def fellow_reviewers(user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    """Lista mínima de revisores (para coordinación de segunda aprobación)."""
    return [{"id": u.id, "full_name": u.full_name} for u in db.scalars(select(User).where(User.role == "REVISOR", User.is_active.is_(True)))]


@router.get("/categories-in-use")
def categories_in_use(user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    ids = _assigned_case_ids(db, user)
    if not ids:
        return []
    cats = db.scalars(select(Category).join(Case, Case.category_id == Category.id).where(Case.id.in_(ids)).distinct()).all()
    return [{"slug": c.slug, "name": c.name} for c in cats]
