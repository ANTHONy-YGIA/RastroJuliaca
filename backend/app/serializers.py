"""Serialización por rol: cada vista expone solo los datos autorizados para quien la solicita."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .models import (
    Case,
    CaseAssignment,
    CaseDecision,
    CaseEvent,
    Category,
    Contribution,
    Correction,
    Observation,
    StoredFile,
    SupportingDocument,
    User,
)
from .security import as_aware, iso, utc
from .services.forms import merged_schema
from .services.policies import POLICY_TEXT, PROTECTED_FLAGS, can_open_contributions, can_publish, effective_sensitivity, floor_for_slug


def user_out(u: User) -> dict:
    return {
        "id": u.id,
        "email": u.email,
        "full_name": u.full_name,
        "role": u.role,
        "alias": u.alias,
        "is_active": u.is_active,
        "can_review_restricted": u.can_review_restricted,
        "can_review_institutional": u.can_review_institutional,
        "created_at": iso(u.created_at),
    }


def category_effective(cat: Category) -> tuple[list[dict], str]:
    parent = cat.parent
    schema = merged_schema(parent.field_schema if parent else None, cat.field_schema or [])
    sens = effective_sensitivity(cat.sensitivity, cat.min_sensitivity, parent.sensitivity if parent else None, [])
    if parent:
        sens = effective_sensitivity(sens, parent.min_sensitivity, None, [])
    return schema, sens


def category_out(cat: Category, with_children: bool = True) -> dict:
    schema, sens = category_effective(cat)
    policy = dict((cat.parent.document_policy if cat.parent else {}) or {})
    policy.update(cat.document_policy or {})
    out = {
        "id": cat.id,
        "slug": cat.slug,
        "name": cat.name,
        "description": cat.description,
        "icon": cat.icon,
        "parent_id": cat.parent_id,
        "sensitivity": sens,
        "configured_sensitivity": cat.sensitivity,
        "min_sensitivity": cat.min_sensitivity,
        "code_floor": floor_for_slug(cat.slug),
        "policy_text": POLICY_TEXT[sens],
        "field_schema": schema,
        "own_field_schema": cat.field_schema or [],
        "document_policy": policy,
        "active": cat.active,
    }
    if with_children:
        out["children"] = [category_out(c, False) for c in sorted(cat.children, key=lambda c: c.sort_order) if c.active]
    return out


def file_out(sf: StoredFile | None) -> dict | None:
    if not sf:
        return None
    return {
        "id": sf.id,
        "original_name": sf.original_name,
        "detected_type": sf.detected_type,
        "media_class": sf.media_class,
        "size_bytes": sf.size_bytes,
        "sha256": sf.sha256,
        "status": sf.status,
        "status_detail": sf.status_detail,
        "scan_engine": sf.scan_engine,
        "scanned_at": iso(sf.scanned_at),
        "has_playback": bool(sf.playback_name),
        "duplicate_of_id": sf.duplicate_of_id,
        "media_info": sf.media_info or {},
        "uploaded_at": iso(sf.uploaded_at),
    }


def case_summary(c: Case) -> dict:
    return {
        "id": c.id,
        "code": c.code,
        "title": c.title,
        "category": {"id": c.category.id, "name": c.category.name, "slug": c.category.slug, "icon": c.category.icon,
                     "parent_name": c.category.parent.name if c.category.parent else None},
        "zone": c.zone,
        "incident_at": iso(c.incident_at),
        "status": c.status,
        "sensitivity": c.sensitivity,
        "publication_status": c.publication_status,
        "contributions_open": c.contributions_open,
        "is_demo": c.is_demo,
        "created_at": iso(c.created_at),
        "submitted_at": iso(c.submitted_at),
    }


def document_out(d: SupportingDocument) -> dict:
    return {
        "id": d.id,
        "doc_type": d.doc_type,
        "description": d.description,
        "review_status": d.review_status,
        "review_note": d.review_note,
        "created_at": iso(d.created_at),
        "file": file_out(d.file),
    }


def event_out(e: CaseEvent, show_actor: bool) -> dict:
    return {
        "id": e.id,
        "event": e.event,
        "detail": e.detail,
        "created_at": iso(e.created_at),
        "actor": (e.actor.full_name if e.actor else "Sistema") if show_actor else None,
    }


def public_card_out(c: Case) -> dict | None:
    pc = c.public_card
    if not pc:
        return None
    return {
        "public_title": pc.public_title,
        "public_summary": pc.public_summary,
        "zone": pc.zone,
        "incident_date": pc.incident_date,
        "public_fields": pc.public_fields,
        "published_at": iso(pc.published_at),
        "withdrawn_at": iso(pc.withdrawn_at),
    }


def flags_out(flags: list[str]) -> list[dict]:
    return [{"key": f, "label": PROTECTED_FLAGS.get(f, f)} for f in flags]


def case_detail(db: Session, c: Case, *, view: str) -> dict:
    """view: owner | reviewer"""
    schema, _ = category_effective(c.category)
    labels = {f["key"]: f["label"] for f in schema}
    out = case_summary(c)
    out.update(
        {
            "description": c.description,
            "specific_fields": c.specific_fields,
            "field_labels": labels,
            "field_schema": schema,
            "private_lat": c.private_lat,
            "private_lon": c.private_lon,
            "private_location_note": c.private_location_note,
            "sensitive_flags": flags_out(c.sensitive_flags or []),
            "status_reason": c.status_reason,
            "policy_text": POLICY_TEXT[c.sensitivity],
            "documents": [document_out(d) for d in c.documents],
            "public_card": public_card_out(c),
            "updated_at": iso(c.updated_at),
            "decided_at": iso(c.decided_at),
        }
    )
    q = select(CaseEvent).where(CaseEvent.case_id == c.id).order_by(CaseEvent.created_at, CaseEvent.id)
    if view == "owner":
        q = q.where(CaseEvent.visible_to_reporter.is_(True))
        out["responsible"] = "Equipo de revisión" if any(a.active for a in c.assignments) else "Pendiente de asignación"
    else:
        assigned = [a.reviewer.full_name for a in c.assignments if a.active]
        out["responsible"] = ", ".join(assigned) or "Sin asignar"
        out["assigned_reviewers"] = [{"id": a.reviewer_id, "full_name": a.reviewer.full_name} for a in c.assignments if a.active]
        out["decisions"] = [
            {"decision": d.decision, "reason": d.reason, "reviewer": d.reviewer.full_name, "reviewer_id": d.reviewer_id, "created_at": iso(d.created_at)}
            for d in db.scalars(select(CaseDecision).where(CaseDecision.case_id == c.id).order_by(CaseDecision.created_at))
        ]
        if c.public_card:
            out["public_card"]["requested_by"] = c.public_card.requested_by
            out["public_card"]["approved_by"] = c.public_card.approved_by
        out["reporter_alias"] = c.reporter.alias
        out["contribution_counts"] = dict(
            db.execute(select(Contribution.status, func.count(Contribution.id)).where(Contribution.case_id == c.id).group_by(Contribution.status)).all()
        )
        out["can_publish"], out["publish_block_reason"] = can_publish(c)
        out["can_open_contributions"], out["contributions_block_reason"] = can_open_contributions(c)
    out["history"] = [event_out(e, view != "owner") for e in db.scalars(q)]
    return out


def corrections_for(db: Session, contribution_id: int) -> list[Correction]:
    return list(db.scalars(select(Correction).where(Correction.contribution_id == contribution_id).order_by(Correction.created_at, Correction.id)))


def effective_values(c: Contribution, corrections: list[Correction]) -> dict:
    vals = {
        "declared_at": iso(c.declared_at),
        "declared_lat": c.declared_lat,
        "declared_lon": c.declared_lon,
        "description": c.description,
    }
    for corr in corrections:
        nv = corr.new_value
        if corr.field in ("declared_lat", "declared_lon"):
            vals[corr.field] = float(nv) if nv not in (None, "") else None
        elif corr.field == "declared_at":
            vals[corr.field] = iso(as_aware(datetime.fromisoformat(nv))) if nv else None
        else:
            vals[corr.field] = nv
    return vals


def contribution_out(db: Session, c: Contribution, *, view: str) -> dict:
    """view: contributor | reviewer"""
    corrs = corrections_for(db, c.id)
    out = {
        "id": c.id,
        "code": c.code,
        "case_id": c.case_id,
        "case_code": c.case.code,
        "case_title": c.case.public_card.public_title if c.case.public_card else c.case.code,
        "type": c.ctype,
        "certainty": c.certainty,
        "status": c.status,
        "classification": c.classification,
        "created_at": iso(c.created_at),
        "original": {
            "declared_at": iso(c.declared_at),
            "declared_lat": c.declared_lat,
            "declared_lon": c.declared_lon,
            "description": c.description,
            "location_note": c.location_note,
        },
        "effective": effective_values(c, corrs),
        "corrections": [
            {"field": x.field, "old_value": x.old_value, "new_value": x.new_value, "reason": x.reason,
             "author": x.author.alias if (view == "reviewer" and x.author_id == c.contributor_id) else (x.author.full_name if view == "reviewer" else ("Usted" if x.author_id == c.contributor_id else "Equipo de revisión")),
             "created_at": iso(x.created_at)}
            for x in corrs
        ],
        "file": file_out(c.file),
    }
    if view == "reviewer":
        out["contributor_alias"] = c.contributor.alias  # se protege la identidad del colaborador
        out["observations"] = [
            {"id": o.id, "text": o.text, "author": o.author.full_name, "created_at": iso(o.created_at)}
            for o in db.scalars(select(Observation).where(Observation.contribution_id == c.id).order_by(Observation.created_at))
        ]
        out["classified_at"] = iso(c.classified_at)
        if c.file and c.file.duplicate_of_id:
            dup = db.scalar(select(Contribution).where(Contribution.file_id == c.file.duplicate_of_id))
            out["duplicate_of_code"] = dup.code if dup else "documento de respaldo del expediente"
    return out


def assignment_names(db: Session, case_id: int) -> list[dict]:
    return [
        {"id": a.reviewer_id, "full_name": a.reviewer.full_name}
        for a in db.scalars(select(CaseAssignment).where(CaseAssignment.case_id == case_id, CaseAssignment.active.is_(True)))
    ]


def to_utc(dt: datetime | None) -> datetime | None:
    return utc(dt)
