"""Dependencias de autenticación, CSRF y autorización por expediente."""
from __future__ import annotations

import hmac
from datetime import datetime, timezone

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .models import SENSITIVITY_ORDER, Case, CaseAssignment, Role, Sensitivity, User, UserSession
from .security import token_digest, utc

SESSION_COOKIE = "rj_session"
CSRF_COOKIE = "rj_csrf"
CSRF_HEADER = "X-CSRF-Token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _load_session(request: Request, db: Session) -> UserSession | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token or len(token) > 200:
        return None
    sess = db.scalar(select(UserSession).where(UserSession.token_hash == token_digest(token)))
    if not sess:
        return None
    if utc(sess.expires_at) < datetime.now(timezone.utc):
        db.delete(sess)
        db.commit()
        return None
    if not sess.user.is_active:
        return None
    return sess


def get_optional_session(request: Request, db: Session = Depends(get_db)) -> UserSession | None:
    sess = _load_session(request, db)
    if sess and request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not hmac.compare_digest(sent, sess.csrf_token):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Token CSRF inválido o ausente")
    return sess


def get_optional_user(sess: UserSession | None = Depends(get_optional_session)) -> User | None:
    return sess.user if sess else None


def get_current_user(sess: UserSession | None = Depends(get_optional_session)) -> User:
    if not sess:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Debe iniciar sesión")
    return sess.user


def require_roles(*roles: Role):
    allowed = {r.value for r in roles}

    def dep(user: User = Depends(get_current_user)) -> User:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "No tiene permisos para esta operación")
        return user

    return dep


require_reviewer = require_roles(Role.REVISOR)
require_admin = require_roles(Role.ADMIN)
require_citizen = require_roles(Role.DENUNCIANTE, Role.COLABORADOR)
require_reporter = require_roles(Role.DENUNCIANTE)


def reviewer_cleared_for(user: User, sensitivity: str) -> bool:
    """Permiso específico para examinar expedientes según su nivel de sensibilidad."""
    if user.role != Role.REVISOR.value:
        return False
    if sensitivity == Sensitivity.INSTITUCIONAL.value:
        return bool(user.can_review_institutional)
    if sensitivity == Sensitivity.RESTRINGIDO.value:
        return bool(user.can_review_restricted or user.can_review_institutional)
    return True


def is_assigned(db: Session, case_id: int, user_id: int) -> bool:
    return (
        db.scalar(
            select(CaseAssignment.id).where(
                CaseAssignment.case_id == case_id,
                CaseAssignment.reviewer_id == user_id,
                CaseAssignment.active.is_(True),
            )
        )
        is not None
    )


def get_case_for_reviewer(db: Session, case_id: int, user: User) -> Case:
    """Protección IDOR: el revisor solo accede a expedientes asignados y para los que tiene habilitación.

    Se responde 404 para no revelar la existencia de expedientes ajenos.
    """
    case = db.get(Case, case_id)
    if not case or not is_assigned(db, case.id, user.id) or not reviewer_cleared_for(user, case.sensitivity):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expediente no encontrado")
    return case


def get_case_for_owner(db: Session, case_id: int, user: User) -> Case:
    case = db.get(Case, case_id)
    if not case or case.reporter_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Expediente no encontrado")
    return case


def max_sensitivity(*levels: str) -> str:
    return max(levels, key=lambda s: SENSITIVITY_ORDER[Sensitivity(s)])
