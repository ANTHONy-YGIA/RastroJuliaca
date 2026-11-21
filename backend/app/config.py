"""Configuración centralizada mediante variables de entorno (prefijo RJ_).

Los valores por defecto son seguros para una demostración local en 127.0.0.1.
Nunca se deben usar los valores por defecto en un despliegue real.
"""
from __future__ import annotations

import shutil
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent

INSECURE_DEFAULT_SECRET = "dev-insecure-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_DIR / ".env"), env_prefix="RJ_", extra="ignore"
    )

    env: str = "development"  # development | test | production
    demo_mode: bool = True
    database_url: str = f"sqlite:///{(PROJECT_DIR / 'data' / 'rastrojuliaca.db').as_posix()}"
    storage_dir: Path = PROJECT_DIR / "data" / "storage"
    secret_key: str = INSECURE_DEFAULT_SECRET

    session_hours: int = 8
    cookie_secure: bool = False  # True cuando se sirva por HTTPS

    # Límites de carga (MB)
    max_image_mb: int = 15
    max_video_mb: int = 200
    max_document_mb: int = 20

    # Antivirus: auto | defender | clamav | none
    av_engine: str = "auto"
    av_timeout_s: int = 180

    # Multimedia
    ffmpeg_path: str = ""
    ffprobe_path: str = ""
    media_timeout_s: int = 240
    max_video_seconds: int = 900
    media_threads: int = 2

    # Rate limiting (peticiones por ventana en segundos)
    rate_login: int = 10
    rate_register: int = 5
    rate_upload: int = 30
    rate_export: int = 30
    rate_window_s: int = 300

    frontend_dist: Path = PROJECT_DIR / "frontend" / "dist"
    process_files_inline: bool = False  # en pruebas se procesa sin tarea en segundo plano

    allowed_hosts: list[str] = Field(default_factory=lambda: ["127.0.0.1", "localhost", "testserver"])

    def resolved_ffmpeg(self) -> str | None:
        return self.ffmpeg_path or shutil.which("ffmpeg")

    def resolved_ffprobe(self) -> str | None:
        return self.ffprobe_path or shutil.which("ffprobe")


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    if s.env == "production":
        if s.secret_key in (INSECURE_DEFAULT_SECRET, "cambie-este-valor") or len(s.secret_key) < 32:
            raise RuntimeError("RJ_SECRET_KEY debe configurarse en producción (mínimo 32 caracteres aleatorios)")
        if s.demo_mode:
            # Las cuentas de demostración usan una contraseña pública: nunca en un despliegue real
            raise RuntimeError("RJ_DEMO_MODE no puede estar activo con RJ_ENV=production")
        if not s.cookie_secure:
            raise RuntimeError("RJ_COOKIE_SECURE=true es obligatorio con RJ_ENV=production (requiere HTTPS)")
    return s
