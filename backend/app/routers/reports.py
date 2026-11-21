"""Informes estructurados con instantánea inmutable, hash de integridad y exportación auditada."""
from __future__ import annotations

import hashlib
import io
import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..audit import audit, case_event
from ..config import get_settings
from ..db import get_db
from ..deps import get_case_for_reviewer, require_reviewer
from ..models import Case, CaseEvent, Contribution, Observation, Report, User
from ..ratelimit import limiter
from ..security import PERU_TZ, iso, utc
from ..serializers import category_effective, corrections_for, effective_values
from ..services.geo import distance_or_none, hours_between
from .public import DISCLAIMER, DOC_TYPES

router = APIRouter(prefix="/api", tags=["informes"])

RELEVANT_EVENTS = {"ENVIADO", "DECISION", "DOCUMENTO_REVISADO", "PUBLICACION", "APORTACIONES", "CLASIFICACION", "CORRECCION", "APORTACION_RECIBIDA"}


class ReportIn(BaseModel):
    title: str = Field(min_length=5, max_length=200)
    summary: str = Field(min_length=20, max_length=5000)
    contribution_ids: list[int] = Field(default_factory=list, max_length=200)
    include_private_locations: bool = False


def canonical(content: dict) -> bytes:
    return json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def build_content(db: Session, case: Case, body: ReportIn, user: User, code: str) -> dict:
    schema, _ = category_effective(case.category)
    labels = {f["key"]: f["label"] for f in schema}
    ids = list(dict.fromkeys(body.contribution_ids))
    contribs = db.scalars(select(Contribution).where(Contribution.id.in_(ids))).all() if ids else []
    if len(contribs) != len(ids) or any(c.case_id != case.id for c in contribs):
        # Aislamiento entre expedientes: no se permite mezclar evidencias
        raise HTTPException(422, "Las evidencias seleccionadas deben pertenecer a este expediente")
    evidence = []
    for c in sorted(contribs, key=lambda x: x.id):
        corrs = corrections_for(db, c.id)
        eff = effective_values(c, corrs)
        when = datetime.fromisoformat(eff["declared_at"].replace("Z", "+00:00")) if eff["declared_at"] else None
        item = {
            "code": c.code,
            "type": c.ctype,
            "status": c.status,
            "classification": c.classification,
            "declared_certainty": c.certainty,
            "description": eff["description"],
            "declared_at": eff["declared_at"],
            "declared_at_original": iso(c.declared_at),
            "received_at": iso(c.created_at),
            "distance_km_approx": distance_or_none(case.private_lat, case.private_lon, eff["declared_lat"], eff["declared_lon"]),
            "time_diff_h": hours_between(utc(case.incident_at), when),
            "corrections": [{"field": x.field, "old_value": x.old_value, "new_value": x.new_value, "reason": x.reason, "at": iso(x.created_at)} for x in corrs],
            "observations": [
                {"text": o.text, "author": o.author.full_name, "at": iso(o.created_at)}
                for o in db.scalars(select(Observation).where(Observation.contribution_id == c.id).order_by(Observation.created_at))
            ],
            "file": None,
        }
        if body.include_private_locations:
            item["declared_location"] = {"lat": eff["declared_lat"], "lon": eff["declared_lon"], "note": c.location_note}
        if c.file:
            item["file"] = {
                "sha256": c.file.sha256,
                "type": c.file.detected_type,
                "size_bytes": c.file.size_bytes,
                "status": c.file.status,
                "antivirus_engine": c.file.scan_engine,
                "scanned_at": iso(c.file.scanned_at),
                "received_at": iso(c.file.uploaded_at),
            }
        evidence.append(item)
    history = [
        {"event": e.event, "detail": e.detail, "at": iso(e.created_at), "actor": e.actor.full_name if e.actor else "Sistema"}
        for e in db.scalars(select(CaseEvent).where(CaseEvent.case_id == case.id).order_by(CaseEvent.created_at, CaseEvent.id))
        if e.event in RELEVANT_EVENTS
    ]
    content = {
        "report_code": code,
        "system": "RastroJuliaca",
        "demo_mode": get_settings().demo_mode,
        "generated_at": iso(datetime.now(timezone.utc)),
        "generated_by": {"name": user.full_name, "role": user.role},
        "title": body.title.strip(),
        "summary": body.summary.strip(),
        "disclaimer": DISCLAIMER + " La información declarada por participantes no constituye un hecho comprobado.",
        "case": {
            "code": case.code,
            "category": case.category.parent.name if case.category.parent else case.category.name,
            "subcategory": case.category.name if case.category.parent else None,
            "sensitivity": case.sensitivity,
            "status": case.status,
            "publication_status": case.publication_status,
            "title": case.title,
            "zone": case.zone,
            "incident_at_declared": iso(case.incident_at),
            "incident_local": utc(case.incident_at).astimezone(PERU_TZ).strftime("%Y-%m-%d %H:%M (UTC-5)"),
            "specific_fields": {labels.get(k, k): v for k, v in (case.specific_fields or {}).items()},
            "supporting_documents": [
                {"type": DOC_TYPES.get(d.doc_type, d.doc_type), "sha256": d.file.sha256, "file_status": d.file.status, "review_status": d.review_status}
                for d in case.documents
            ],
        },
        "evidence": evidence,
        "history": history,
    }
    if body.include_private_locations:
        content["case"]["private_location"] = {"lat": case.private_lat, "lon": case.private_lon, "note": case.private_location_note}
    return content


@router.post("/review/cases/{case_id}/reports", status_code=201)
def create_report(case_id: int, body: ReportIn, request: Request, user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    case = get_case_for_reviewer(db, case_id, user)
    report = Report(code="tmp", case_id=case.id, created_by=user.id, title=body.title.strip(), content={}, content_sha256="")
    db.add(report)
    db.flush()
    report.code = f"IN-{datetime.now(timezone.utc).year}-{report.id:05d}"
    content = build_content(db, case, body, user, report.code)
    report.content = content
    report.content_sha256 = hashlib.sha256(canonical(content)).hexdigest()
    case_event(db, case.id, "INFORME", f"Informe {report.code} generado con {len(content['evidence'])} evidencia(s)", user, visible_to_reporter=False)
    audit(db, "REPORT_CREATED", user, "report", report.id, request, case_id=case.id, evidence=len(content["evidence"]), sha256=report.content_sha256)
    db.commit()
    return _report_out(report)


def _report_out(r: Report) -> dict:
    return {
        "id": r.id,
        "code": r.code,
        "case_id": r.case_id,
        "title": r.title,
        "created_at": iso(r.created_at),
        "created_by": r.author.full_name if r.author else None,
        "content_sha256": r.content_sha256,
        "export_count": r.export_count,
        "content": r.content,
    }


@router.get("/review/reports")
def list_reports(case_id: int | None = None, user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    from .review import _assigned_case_ids

    ids = _assigned_case_ids(db, user)
    if case_id is not None:
        ids = [i for i in ids if i == case_id]
    if not ids:
        return []
    rows = db.scalars(select(Report).where(Report.case_id.in_(ids)).order_by(Report.created_at.desc())).all()
    return [{k: v for k, v in _report_out(r).items() if k != "content"} | {"case_code": r.case.code} for r in rows]


def _report_for(db: Session, report_id: int, user: User) -> Report:
    r = db.get(Report, report_id)
    if not r:
        raise HTTPException(404, "Informe no encontrado")
    get_case_for_reviewer(db, r.case_id, user)
    return r


@router.get("/reports/{report_id}")
def get_report(report_id: int, user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    return _report_out(_report_for(db, report_id, user))


def _register_export(db: Session, r: Report, user: User, request: Request, fmt: str) -> None:
    s = get_settings()
    limiter.check(f"export:{user.id}", s.rate_export, s.rate_window_s)
    r.export_count += 1
    audit(db, "REPORT_EXPORTED", user, "report", r.id, request, format=fmt, sha256=r.content_sha256)
    db.commit()


@router.get("/reports/{report_id}/export.json")
def export_json(report_id: int, request: Request, user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    r = _report_for(db, report_id, user)
    _register_export(db, r, user, request, "json")
    payload = {
        "report": r.content,
        "integrity": {"algorithm": "SHA-256", "canonicalization": "JSON UTF-8, claves ordenadas, sin espacios", "content_sha256": r.content_sha256},
        "exported_at": iso(datetime.now(timezone.utc)),
        "exported_by": user.full_name,
    }
    return Response(
        json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="{r.code}.json"', "Cache-Control": "no-store"},
    )


@router.get("/reports/{report_id}/export.pdf")
def export_pdf(report_id: int, request: Request, user: User = Depends(require_reviewer), db: Session = Depends(get_db)):
    r = _report_for(db, report_id, user)
    _register_export(db, r, user, request, "pdf")
    pdf = render_pdf(r)
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="{r.code}.pdf"', "Cache-Control": "no-store"})


def render_pdf(r: Report) -> bytes:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    c = r.content
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=r.code, author="RastroJuliaca")
    ss = getSampleStyleSheet()
    navy = colors.HexColor("#0B2545")
    h1 = ParagraphStyle("h1", parent=ss["Heading1"], textColor=navy, fontSize=16)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=navy, fontSize=12, spaceBefore=8)
    body = ParagraphStyle("b", parent=ss["BodyText"], fontSize=9, leading=12)
    small = ParagraphStyle("s", parent=body, fontSize=7.5, leading=9, textColor=colors.HexColor("#475569"))

    def P(t, st=body):
        return Paragraph(escape(str(t if t is not None else "—")), st)

    story = [P(f"RastroJuliaca — Informe {c['report_code']}", h1)]
    if c.get("demo_mode"):
        story.append(P("MODO DEMOSTRACIÓN — datos ficticios", ParagraphStyle("d", parent=body, textColor=colors.HexColor("#B45309"))))
    story += [P(c["title"], h2), P(c["summary"]), Spacer(1, 4), P(c["disclaimer"], small)]
    cs = c["case"]
    rows = [["Expediente", cs["code"]], ["Categoría", f"{cs['category']}" + (f" / {cs['subcategory']}" if cs.get("subcategory") else "")],
            ["Sensibilidad", cs["sensitivity"]], ["Estado", cs["status"]], ["Zona", cs["zone"]], ["Incidente (declarado)", cs["incident_local"]]]
    rows += [[k, v] for k, v in cs.get("specific_fields", {}).items()]
    story.append(P("Datos del expediente", h2))
    t = Table([[P(a), P(b)] for a, b in rows], colWidths=[45 * mm, 125 * mm])
    t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")), ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#F1F5F9")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(t)
    story.append(P(f"Evidencias seleccionadas ({len(c['evidence'])})", h2))
    for e in c["evidence"]:
        story.append(P(f"{e['code']} · {e['type']} · {e['classification'] or e['status']} · certeza declarada {e['declared_certainty']}", ParagraphStyle("eb", parent=body, fontName="Helvetica-Bold")))
        story.append(P(e["description"]))
        meta = f"Hora declarada: {e['declared_at'] or 'sin dato'} · Distancia aprox.: {e['distance_km_approx'] if e['distance_km_approx'] is not None else 'datos insuficientes'} km · Δt: {e['time_diff_h'] if e['time_diff_h'] is not None else 'datos insuficientes'} h"
        story.append(P(meta, small))
        if e.get("file"):
            story.append(P(f"SHA-256: {e['file']['sha256']} · Antivirus: {e['file']['antivirus_engine']}", small))
        for o in e["observations"]:
            story.append(P(f"Observación ({o['author']}): {o['text']}", small))
        for x in e["corrections"]:
            story.append(P(f"Corrección {x['field']}: {x['old_value']} → {x['new_value']} ({x['reason']})", small))
        story.append(Spacer(1, 5))
    story.append(P("Historial pertinente", h2))
    for h in c["history"]:
        story.append(P(f"{h['at']} · {h['event']} · {h['detail']} ({h['actor']})", small))
    story.append(Spacer(1, 8))
    story.append(P(f"Integridad: SHA-256 del contenido canónico = {r.content_sha256}", small))
    doc.build(story)
    return buf.getvalue()
