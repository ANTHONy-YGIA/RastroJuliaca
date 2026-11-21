from __future__ import annotations

from fastapi import Request
from sqlalchemy.orm import Session

from .models import AuditLog, CaseEvent, Notification, User
from .ratelimit import client_ip


def audit(
    db: Session,
    action: str,
    actor: User | None = None,
    entity_type: str | None = None,
    entity_id: str | int | None = None,
    request: Request | None = None,
    **details,
) -> None:
    db.add(
        AuditLog(
            action=action,
            actor_id=actor.id if actor else None,
            entity_type=entity_type,
            entity_id=str(entity_id) if entity_id is not None else None,
            ip=client_ip(request) if request else None,
            details=details,
        )
    )


def case_event(db: Session, case_id: int, event: str, detail: str = "", actor: User | None = None, visible_to_reporter: bool = True) -> None:
    db.add(CaseEvent(case_id=case_id, event=event, detail=detail, actor_id=actor.id if actor else None, visible_to_reporter=visible_to_reporter))


def notify(db: Session, user_id: int, title: str, body: str = "", link: str | None = None) -> None:
    db.add(Notification(user_id=user_id, title=title, body=body, link=link))
