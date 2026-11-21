"""Pruebas de las correcciones de la auditoría (límite de cuerpo, guardas de producción, cuarentena detenida)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.config import Settings
from app.models import Role, StoredFile
from conftest import Actor, contribute, make_staff, register


def test_cuerpo_excesivo_rechazado_antes_de_procesar(flow):
    from app.main import MAX_BODY_BYTES

    col = register("col@prueba.test", "COLABORADOR")
    r = col.post("/api/contributions", content=b"x", headers={"Content-Length": str(MAX_BODY_BYTES + 1), "Content-Type": "multipart/form-data; boundary=x"})
    assert r.status_code == 413


def test_guardas_de_produccion(monkeypatch):
    from app import config

    def build(**kw):
        config.get_settings.cache_clear()
        for k, v in kw.items():
            monkeypatch.setenv(k, v)
        try:
            return config.get_settings()
        finally:
            config.get_settings.cache_clear()

    strong = "x" * 48
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        build(RJ_ENV="production", RJ_SECRET_KEY="cambie-este-valor")
    with pytest.raises(RuntimeError, match="DEMO_MODE"):
        build(RJ_ENV="production", RJ_SECRET_KEY=strong, RJ_DEMO_MODE="true")
    with pytest.raises(RuntimeError, match="COOKIE_SECURE"):
        build(RJ_ENV="production", RJ_SECRET_KEY=strong, RJ_DEMO_MODE="false", RJ_COOKIE_SECURE="false")
    ok = build(RJ_ENV="production", RJ_SECRET_KEY=strong, RJ_DEMO_MODE="false", RJ_COOKIE_SECURE="true")
    assert isinstance(ok, Settings)


def test_reanalisis_de_cuarentena_detenida(flow):
    from app.db import SessionLocal
    from app.services import antivirus
    from conftest import CleanTestScanner

    antivirus.set_scanner_override(None)
    col = register("col@prueba.test", "COLABORADOR")
    c = contribute(col, flow["case"]["code"]).json()
    fid = c["file"]["id"]
    admin = make_staff("admin@prueba.test", Role.ADMIN)
    # Simula un procesamiento interrumpido: el archivo quedó en cuarentena
    with SessionLocal() as db:
        sf = db.get(StoredFile, fid)
        sf.status = "CUARENTENA"
        db.commit()
    assert admin.post(f"/api/admin/files/{fid}/rescan").status_code == 409  # reciente: aún puede estar procesándose
    with SessionLocal() as db:
        db.get(StoredFile, fid).uploaded_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        db.commit()
    antivirus.set_scanner_override(CleanTestScanner())
    assert admin.post(f"/api/admin/files/{fid}/rescan").status_code == 200
    assert flow["rev"].get(f"/api/review/contributions/{c['id']}").json()["file"]["status"] == "DISPONIBLE"
    assert Actor().get("/api/health").status_code == 200
