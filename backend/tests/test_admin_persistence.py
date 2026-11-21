from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, inspect, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Case, Role
from conftest import Actor, PASSWORD, contribute, create_case, make_staff, register


def test_asignaciones_y_usuarios():
    admin = make_staff("admin@prueba.test", Role.ADMIN)
    r = admin.post("/api/admin/users", json={"email": "nuevo@prueba.test", "full_name": "Nuevo Revisor", "password": PASSWORD, "role": "REVISOR"})
    assert r.status_code == 201
    uid = r.json()["id"]
    r = admin.post("/api/admin/users", json={"email": "adm2@prueba.test", "full_name": "Admin 2", "password": PASSWORD, "role": "ADMIN", "can_review_institutional": True})
    assert r.status_code == 422  # administración separada del examen de evidencias
    assert admin.patch(f"/api/admin/users/{uid}", json={"can_review_restricted": True}).json()["can_review_restricted"] is True
    rev = Actor().login("nuevo@prueba.test")
    assert admin.patch(f"/api/admin/users/{uid}", json={"is_active": False}).status_code == 200
    assert rev.get("/api/auth/me").status_code == 401  # sesiones revocadas
    assert admin.patch(f"/api/admin/users/{admin.user['id']}", json={"is_active": False}).status_code == 409


def test_solicitud_de_derechos_y_anonimizacion():
    admin = make_staff("admin@prueba.test", Role.ADMIN)
    rep = register("titular@prueba.test", name="Titular Real")
    create_case(rep)
    exp = rep.get("/api/me/export")
    assert exp.status_code == 200 and "Titular Real" in exp.text
    r = rep.post("/api/me/data-requests", json={"rtype": "CANCELACION", "detail": "Solicito la cancelación de mis datos personales."})
    rid = r.json()["id"]
    reqs = admin.get("/api/admin/data-requests").json()
    assert reqs[0]["rtype"] == "CANCELACION"
    r = admin.post(f"/api/admin/data-requests/{rid}/resolve", json={"status": "ATENDIDA", "response": "Se anonimizó la cuenta del titular.", "anonymize_account": True})
    assert r.status_code == 200
    assert rep.get("/api/auth/me").status_code == 401
    users = admin.get("/api/admin/users").json()
    assert not any(u["email"] == "titular@prueba.test" for u in users)
    assert admin.post(f"/api/admin/data-requests/{rid}/resolve", json={"status": "ATENDIDA", "response": "Repetido de nuevo"}).status_code == 409


def test_politica_de_conservacion(flow):
    admin = make_staff("admin@prueba.test", Role.ADMIN)
    rev = flow["rev"]
    rev.post(f"/api/review/cases/{flow['case']['id']}/decision", json={"decision": "CERRAR", "reason": "Gestión concluida"})
    assert admin.put("/api/admin/settings", json={"retention_days_closed": 10}).status_code == 422  # mínimo 30
    assert admin.put("/api/admin/settings", json={"retention_days_closed": 30}).json()["retention_days_closed"] == 30
    from app.db import SessionLocal

    with SessionLocal() as db:
        c = db.get(Case, flow["case"]["id"])
        c.decided_at = datetime.now(timezone.utc) - timedelta(days=40)
        db.commit()
    dry = admin.post("/api/admin/retention/run", json={"dry_run": True}).json()
    assert dry["cases"] == [flow["case"]["code"]] and dry["files_deleted"] == 0
    real = admin.post("/api/admin/retention/run", json={"dry_run": False}).json()
    assert real["files_deleted"] == 2
    detail = rev.get(f"/api/review/cases/{flow['case']['id']}").json()
    assert detail["documents"][0]["file"]["status"] == "ELIMINADO"
    assert detail["private_lat"] is None
    assert any(e["action"] == "RETENTION_RUN" for e in admin.get("/api/admin/audit").json())


def test_persistencia_tras_reinicio(flow):
    """Simula un reinicio: un motor nuevo sobre el mismo archivo SQLite recupera los datos."""
    from app.config import get_settings

    code = flow["case"]["code"]
    eng = create_engine(get_settings().database_url)
    with sessionmaker(bind=eng)() as db:
        assert db.scalar(select(Case.code).where(Case.code == code)) == code
    eng.dispose()
    assert Actor().get(f"/api/public/cases/{code}").status_code == 200


def test_migraciones_alembic_coinciden_con_modelos(tmp_path):
    from alembic import command
    from alembic.config import Config

    from app.config import BACKEND_DIR

    url = f"sqlite:///{(tmp_path / 'mig.db').as_posix()}"
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.attributes["configure_logger"] = False
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
    eng = create_engine(url)
    tables = set(inspect(eng).get_table_names()) - {"alembic_version"}
    assert tables == set(Base.metadata.tables)
    eng.dispose()


def test_aviso_en_meta_y_modo_demo():
    meta = Actor().get("/api/meta").json()
    assert "no reemplaza a la Policía Nacional del Perú" in meta["disclaimer"]
    assert meta["antivirus"]["available"] is False  # en pruebas RJ_AV_ENGINE=none
    assert "Centro de Juliaca" in meta["zones"]
