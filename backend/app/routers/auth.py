from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from ..audit import audit
from ..config import get_settings
from ..db import get_db
from ..deps import CSRF_COOKIE, SESSION_COOKIE, get_current_user, get_optional_session
from ..models import Notification, Role, User, UserSession
from ..ratelimit import client_ip, limiter
from ..security import (
    DUMMY_HASH,
    PASSWORD_RULES,
    hash_password,
    make_alias,
    new_token,
    password_is_strong,
    token_digest,
    utc,
    verify_password,
)
from ..serializers import user_out

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=10, max_length=128)
    role: Literal["DENUNCIANTE", "COLABORADOR"]
    accept_terms: bool


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


def _set_session(db: Session, response: Response, request: Request, user: User) -> UserSession:
    s = get_settings()
    token = new_token()
    sess = UserSession(
        token_hash=token_digest(token),
        csrf_token=new_token(),
        user_id=user.id,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=s.session_hours),
        ip=client_ip(request),
        user_agent=(request.headers.get("user-agent") or "")[:255],
    )
    db.add(sess)
    max_age = s.session_hours * 3600
    response.set_cookie(SESSION_COOKIE, token, max_age=max_age, httponly=True, secure=s.cookie_secure, samesite="strict", path="/")
    # Cookie legible por JS para el patrón "double submit"; el servidor la compara con la sesión
    response.set_cookie(CSRF_COOKIE, sess.csrf_token, max_age=max_age, httponly=False, secure=s.cookie_secure, samesite="strict", path="/")
    return sess


def me_payload(db: Session, user: User, sess: UserSession) -> dict:
    unread = db.scalar(select(func.count(Notification.id)).where(Notification.user_id == user.id, Notification.read_at.is_(None)))
    return {"user": user_out(user), "csrf_token": sess.csrf_token, "unread_notifications": unread}


@router.post("/register", status_code=201)
def register(body: RegisterIn, request: Request, response: Response, db: Session = Depends(get_db)):
    s = get_settings()
    limiter.check(f"register:{client_ip(request)}", s.rate_register, s.rate_window_s)
    if not body.accept_terms:
        raise HTTPException(422, "Debe aceptar el aviso de privacidad y los términos de uso")
    if not password_is_strong(body.password):
        raise HTTPException(422, PASSWORD_RULES)
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "Ya existe una cuenta con ese correo")
    user = User(email=email, full_name=body.full_name.strip(), password_hash=hash_password(body.password), role=body.role, alias="tmp")
    db.add(user)
    db.flush()
    user.alias = make_alias(user.id)
    sess = _set_session(db, response, request, user)
    audit(db, "USER_REGISTERED", user, "user", user.id, request, role=user.role)
    db.commit()
    return me_payload(db, user, sess)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    s = get_settings()
    limiter.check(f"login:{client_ip(request)}", s.rate_login, s.rate_window_s)
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    now = datetime.now(timezone.utc)
    if user and user.locked_until and utc(user.locked_until) > now:
        raise HTTPException(status.HTTP_423_LOCKED, "Cuenta bloqueada temporalmente por intentos fallidos")
    ok = verify_password(body.password, user.password_hash if user else DUMMY_HASH)
    if not user or not ok or not user.is_active:
        if user:
            user.failed_logins += 1
            if user.failed_logins >= 5:
                user.locked_until = now + timedelta(minutes=15)
                user.failed_logins = 0
            audit(db, "LOGIN_FAILED", user, "user", user.id, request)
            db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Credenciales inválidas")
    user.failed_logins = 0
    user.locked_until = None
    # Limpieza de sesiones expiradas del usuario
    db.execute(delete(UserSession).where(UserSession.user_id == user.id, UserSession.expires_at < now))
    sess = _set_session(db, response, request, user)
    audit(db, "LOGIN", user, "user", user.id, request)
    db.commit()
    return me_payload(db, user, sess)


@router.post("/logout")
def logout(request: Request, response: Response, sess: UserSession | None = Depends(get_optional_session), db: Session = Depends(get_db)):
    if sess:
        audit(db, "LOGOUT", sess.user, "user", sess.user_id, request)
        db.delete(sess)
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(user: User = Depends(get_current_user), sess: UserSession = Depends(get_optional_session), db: Session = Depends(get_db)):
    return me_payload(db, user, sess)
