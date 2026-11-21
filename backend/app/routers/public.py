"""Endpoints públicos: metadatos, categorías y fichas públicas generalizadas."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..models import Case, Category, Contribution, PublicCard, PublicationStatus
from ..security import iso
from ..serializers import category_out
from ..services.antivirus import get_scanner
from ..services.policies import POLICY_TEXT, PROTECTED_FLAGS, accepts_contributions

router = APIRouter(prefix="/api", tags=["público"])

ZONES = [
    "Centro de Juliaca",
    "Zona Norte",
    "Zona Sur",
    "Zona Este",
    "Zona Oeste",
    "Salida a Puno",
    "Salida a Cusco",
    "Salida a Arequipa",
    "Salida a Huancané",
    "Sector aeropuerto",
    "Mercados y comercio",
    "Otra zona de la provincia de San Román",
]

DOC_TYPES = {
    "DENUNCIA_POLICIAL": "Copia de denuncia policial",
    "CONSTANCIA_AUTORIDAD": "Constancia de autoridad u organismo",
    "DECLARACION_JURADA": "Declaración jurada del denunciante",
    "DOCUMENTO_PROPIEDAD": "Documento de propiedad (tarjeta, boleta, factura)",
    "FOTOGRAFIA_RESPALDO": "Fotografía de respaldo",
    "VIDEO_RESPALDO": "Video de respaldo",
    "INFORME_MEDICO": "Informe o constancia médica",
    "OTRO": "Otro documento",
}

DISCLAIMER = (
    "RastroJuliaca no reemplaza a la Policía Nacional del Perú, no certifica denuncias, no determina "
    "culpabilidad y no garantiza la resolución de incidentes. La publicación de una ficha no significa "
    "que los hechos hayan sido verificados por una autoridad."
)


@router.get("/meta")
def meta():
    s = get_settings()
    scanner = get_scanner()
    return {
        "app": "RastroJuliaca",
        "demo_mode": s.demo_mode,
        "zones": ZONES,
        "doc_types": DOC_TYPES,
        "protected_flags": PROTECTED_FLAGS,
        "policy_text": POLICY_TEXT,
        "disclaimer": DISCLAIMER,
        "limits_mb": {"image": s.max_image_mb, "video": s.max_video_mb, "document": s.max_document_mb},
        "antivirus": {"engine": scanner.name, "available": scanner.available()},
        "ffmpeg_available": bool(s.resolved_ffmpeg() and s.resolved_ffprobe()),
    }


@router.get("/categories")
def list_categories(db: Session = Depends(get_db)):
    cats = db.scalars(select(Category).where(Category.parent_id.is_(None), Category.active.is_(True)).order_by(Category.sort_order)).all()
    return [category_out(c) for c in cats]


@router.get("/categories/{category_id}")
def get_category(category_id: int, db: Session = Depends(get_db)):
    c = db.get(Category, category_id)
    if not c or not c.active:
        raise HTTPException(404, "Categoría no encontrada")
    return category_out(c)


def _public_case_out(c: Case, contributions: int | None = None) -> dict:
    pc = c.public_card
    out = {
        "code": c.code,
        "public_title": pc.public_title,
        "public_summary": pc.public_summary,
        "zone": pc.zone,
        "incident_date": pc.incident_date,
        "category": {"name": c.category.name, "slug": c.category.slug, "icon": c.category.icon,
                     "parent_name": c.category.parent.name if c.category.parent else None},
        "sensitivity": c.sensitivity,
        "public_fields": pc.public_fields,
        "published_at": iso(pc.published_at),
        "accepts_contributions": accepts_contributions(c),
        "is_demo": c.is_demo,
    }
    if contributions is not None:
        out["contributions_received"] = contributions
    return out


def _published_query():
    return (
        select(Case)
        .join(PublicCard, PublicCard.case_id == Case.id)
        .where(Case.publication_status == PublicationStatus.PUBLICADO.value, PublicCard.withdrawn_at.is_(None))
    )


@router.get("/public/cases")
def public_cases(
    q: str | None = Query(default=None, max_length=100),
    category: str | None = Query(default=None, max_length=80),
    zone: str | None = Query(default=None, max_length=80),
    open_only: bool = False,
    db: Session = Depends(get_db),
):
    stmt = _published_query()
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(PublicCard.public_title.ilike(like), PublicCard.public_summary.ilike(like), Case.code.ilike(like)))
    if zone:
        stmt = stmt.where(PublicCard.zone == zone)
    if open_only:
        stmt = stmt.where(Case.contributions_open.is_(True))
    cases = db.scalars(stmt.order_by(PublicCard.published_at.desc())).all()
    if category:
        cases = [c for c in cases if c.category.slug == category or (c.category.parent and c.category.parent.slug == category)]
    return [_public_case_out(c) for c in cases]


@router.get("/public/cases/{code}")
def public_case(code: str, db: Session = Depends(get_db)):
    c = db.scalar(_published_query().where(Case.code == code))
    if not c:
        raise HTTPException(404, "Ficha pública no encontrada")
    n = db.scalar(select(func.count(Contribution.id)).where(Contribution.case_id == c.id))
    return _public_case_out(c, n)


@router.get("/public/stats")
def public_stats(db: Session = Depends(get_db)):
    published = db.scalar(select(func.count(Case.id)).where(Case.publication_status == PublicationStatus.PUBLICADO.value))
    open_cases = db.scalar(
        select(func.count(Case.id)).where(Case.publication_status == PublicationStatus.PUBLICADO.value, Case.contributions_open.is_(True))
    )
    categories = db.scalar(select(func.count(Category.id)).where(Category.parent_id.is_(None), Category.active.is_(True)))
    return {"published_cases": published, "open_for_contributions": open_cases, "categories": categories}
