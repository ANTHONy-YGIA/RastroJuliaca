"""Hash de contraseñas (Argon2id), tokens de sesión y utilidades de tiempo."""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from datetime import datetime, timedelta, timezone

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .config import get_settings

_hasher = PasswordHasher()  # Argon2id con parámetros por defecto de argon2-cffi

PERU_TZ = timezone(timedelta(hours=-5), name="America/Lima")  # Perú no usa horario de verano

PASSWORD_RULES = "Mínimo 10 caracteres, con al menos una letra y un número."


def password_is_strong(pw: str) -> bool:
    return len(pw) >= 10 and re.search(r"[A-Za-z]", pw) is not None and re.search(r"\d", pw) is not None


def hash_password(pw: str) -> str:
    return _hasher.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return _hasher.verify(hashed, pw)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


# Hash ficticio para igualar tiempos cuando el usuario no existe
DUMMY_HASH = _hasher.hash("rastrojuliaca-dummy-password-1")


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    """HMAC-SHA256 del token de sesión: la base de datos nunca guarda el token en claro."""
    key = get_settings().secret_key.encode()
    return hmac.new(key, token.encode(), hashlib.sha256).hexdigest()


def utc(dt: datetime | None) -> datetime | None:
    """Normaliza a UTC consciente de zona (SQLite devuelve fechas sin zona)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def iso(dt: datetime | None) -> str | None:
    d = utc(dt)
    return d.isoformat().replace("+00:00", "Z") if d else None


def as_aware(dt: datetime | None) -> datetime | None:
    """Entradas sin zona horaria se interpretan como hora de Perú (UTC-5)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=PERU_TZ)
    return dt.astimezone(timezone.utc)


def make_alias(user_id: int) -> str:
    digest = hmac.new(get_settings().secret_key.encode(), f"alias:{user_id}:{secrets.token_hex(4)}".encode(), hashlib.sha256)
    return "COL-" + digest.hexdigest()[:6].upper()
