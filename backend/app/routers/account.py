"""Cuenta del usuario: notificaciones internas, exportación de datos propios y solicitudes de derechos."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

import json

from ..audit import audit, notify
from ..db import get_db
from ..deps import get_current_user
from ..models import Case, Contribution, DataRightsRequest, Notification, Role, User
from ..security import iso
from ..serializers import user_out

router = APIRouter(prefix="/api/me", tags=["cuenta"])


@router.get("/notifications")
def notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(50)).all()
    return [{"id": n.id, "title": n.title, "body": n.body, "link": n.link, "created_at": iso(n.created_at), "read": n.read_at is not None} for n in rows]


@router.post("/notifications/{nid}/read")
def mark_read(nid: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.get(Notification, nid)
    if not n or n.user_id != user.id:
        raise HTTPException(404, "Notificación no encontrada")
    n.read_at = n.read_at or datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


@router.post("/notifications/read-all")
def mark_all_read(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    db.execute(update(Notification).where(Notification.user_id == user.id, Notification.read_at.is_(None)).values(read_at=datetime.now(timezone.utc)))
    db.commit()
    return {"ok": True}


@router.get("/export")
def export_my_data(request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Derecho de acceso: el titular descarga los datos personales que el sistema conserva sobre él."""
    data = {
        "account": user_out(user),
        "cases": [
            {"code": c.code, "title": c.title, "status": c.status, "created_at": iso(c.created_at), "zone": c.zone,
             "description": c.description, "private_lat": c.private_lat, "private_lon": c.private_lon}
            for c in db.scalars(select(Case).where(Case.reporter_id == user.id))
        ],
        "contributions": [
            {"code": c.code, "type": c.ctype, "status": c.status, "description": c.description, "declared_at": iso(c.declared_at),
             "declared_lat": c.declared_lat, "declared_lon": c.declared_lon, "created_at": iso(c.created_at)}
            for c in db.scalars(select(Contribution).where(Contribution.contributor_id == user.id))
        ],
        "data_rights_requests": [
            {"type": r.rtype, "status": r.status, "created_at": iso(r.created_at), "response": r.response}
            for r in db.scalars(select(DataRightsRequest).where(DataRightsRequest.user_id == user.id))
        ],
        "exported_at": iso(datetime.now(timezone.utc)),
    }
    audit(db, "PERSONAL_DATA_EXPORTED", user, "user", user.id, request)
    db.commit()
    return Response(json.dumps(data, ensure_ascii=False, indent=2), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="mis-datos-rastrojuliaca.json"', "Cache-Control": "no-store"})


class RightsIn(BaseModel):
    rtype: Literal["ACCESO", "RECTIFICACION", "CANCELACION", "OPOSICION"]
    detail: str = Field(min_length=10, max_length=2000)


@router.post("/data-requests", status_code=201)
def create_rights_request(body: RightsIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    r = DataRightsRequest(user_id=user.id, rtype=body.rtype, detail=body.detail.strip())
    db.add(r)
    db.flush()
    for admin in db.scalars(select(User).where(User.role == Role.ADMIN.value, User.is_active.is_(True))):
        notify(db, admin.id, "Nueva solicitud de derechos del titular", f"Solicitud #{r.id} ({body.rtype})", "/admin")
    audit(db, "DATA_RIGHTS_REQUESTED", user, "data_request", r.id, request, rtype=body.rtype)
    db.commit()
    return {"id": r.id, "rtype": r.rtype, "status": r.status, "created_at": iso(r.created_at)}


@router.get("/data-requests")
def my_rights_requests(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return [
        {"id": r.id, "rtype": r.rtype, "detail": r.detail, "status": r.status, "response": r.response, "created_at": iso(r.created_at), "resolved_at": iso(r.resolved_at)}
        for r in db.scalars(select(DataRightsRequest).where(DataRightsRequest.user_id == user.id).order_by(DataRightsRequest.created_at.desc()))
    ]
