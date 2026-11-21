"""Configuración de pruebas: BD y almacenamiento temporales, procesamiento de archivos en línea.

El antivirus por defecto en pruebas es "none" (archivos quedan BLOQUEADOS). Las pruebas que necesitan
archivos disponibles usan explícitamente ``clean_scanner`` (doble de prueba declarado) o el motor real
de Microsoft Defender en ``test_real_tools.py``.
"""
from __future__ import annotations

import io
import os
import shutil
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="rj-tests-"))
os.environ.update(
    {
        "RJ_ENV": "test",
        "RJ_DATABASE_URL": f"sqlite:///{(_TMP / 'test.db').as_posix()}",
        "RJ_STORAGE_DIR": str(_TMP / "storage"),
        "RJ_PROCESS_FILES_INLINE": "true",
        "RJ_AV_ENGINE": "none",
        "RJ_SECRET_KEY": "test-secret-key-not-for-production",
        "RJ_DEMO_MODE": "false",
        "RJ_MAX_IMAGE_MB": "1",
        "RJ_RATE_LOGIN": "1000",
        "RJ_RATE_REGISTER": "1000",
        "RJ_RATE_UPLOAD": "1000",
    }
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Role, User  # noqa: E402
from app.ratelimit import limiter  # noqa: E402
from app.security import hash_password, make_alias  # noqa: E402
from app.seed import ensure_categories  # noqa: E402
from app.services import antivirus  # noqa: E402

PASSWORD = "Prueba-Segura-2026"


class CleanTestScanner(antivirus.Scanner):
    """DOBLE DE PRUEBA: solo se usa en pruebas automatizadas, nunca en la aplicación."""

    name = "DOBLE-DE-PRUEBA (solo tests)"

    def available(self) -> bool:
        return True

    def scan(self, path):
        return antivirus.ScanResult("clean", self.name, "doble de prueba")


class InfectedTestScanner(CleanTestScanner):
    def scan(self, path):
        return antivirus.ScanResult("infected", self.name, "doble de prueba: amenaza")


@pytest.fixture(autouse=True)
def fresh_db():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    storage_dir = Path(os.environ["RJ_STORAGE_DIR"])
    if storage_dir.exists():
        shutil.rmtree(storage_dir)
    with SessionLocal() as db:
        ensure_categories(db)
    limiter.reset()
    antivirus.set_scanner_override(None)
    yield
    antivirus.set_scanner_override(None)


@pytest.fixture
def clean_scanner():
    antivirus.set_scanner_override(CleanTestScanner())
    yield
    antivirus.set_scanner_override(None)


class Actor:
    """Cliente HTTP con su propia sesión (cookies) y token CSRF."""

    def __init__(self, user: dict | None = None):
        self.client = TestClient(app, base_url="http://testserver")
        self.csrf = ""
        self.user = user

    def _h(self, kw):
        h = kw.pop("headers", {}) or {}
        if self.csrf:
            h["X-CSRF-Token"] = self.csrf
        return h

    def get(self, url, **kw):
        return self.client.get(url, **kw)

    def post(self, url, **kw):
        return self.client.post(url, headers=self._h(kw), **kw)

    def patch(self, url, **kw):
        return self.client.patch(url, headers=self._h(kw), **kw)

    def put(self, url, **kw):
        return self.client.put(url, headers=self._h(kw), **kw)

    def delete(self, url, **kw):
        return self.client.delete(url, headers=self._h(kw), **kw)

    def login(self, email: str, password: str = PASSWORD) -> "Actor":
        r = self.client.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        self.csrf = r.json()["csrf_token"]
        self.user = r.json()["user"]
        return self


def register(email: str, role: str = "DENUNCIANTE", name: str = "Persona de Prueba") -> Actor:
    a = Actor()
    r = a.client.post("/api/auth/register", json={"email": email, "full_name": name, "password": PASSWORD, "role": role, "accept_terms": True})
    assert r.status_code == 201, r.text
    a.csrf = r.json()["csrf_token"]
    a.user = r.json()["user"]
    return a


def make_staff(email: str, role: Role, restricted: bool = False, institutional: bool = False, name: str | None = None) -> Actor:
    with SessionLocal() as db:
        u = User(email=email, full_name=name or email.split("@")[0], password_hash=hash_password(PASSWORD), role=role.value, alias="tmp",
                 can_review_restricted=restricted, can_review_institutional=institutional)
        db.add(u)
        db.flush()
        u.alias = make_alias(u.id)
        db.commit()
    return Actor().login(email)


def png_bytes(color=(10, 120, 200), size=(64, 48)) -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "PNG")
    return buf.getvalue()


def pdf_bytes(text: str = "documento") -> bytes:
    body = f"%PDF-1.4\n1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] >> endobj\n% {text}\ntrailer << /Root 1 0 R >>\n%%EOF\n"
    return body.encode()


def category_id(actor: Actor, slug: str) -> int:
    for c in actor.get("/api/categories").json():
        if c["slug"] == slug:
            return c["id"]
        for ch in c["children"]:
            if ch["slug"] == slug:
                return ch["id"]
    raise KeyError(slug)


VEHICLE_FIELDS = {"tipo_vehiculo": "Mototaxi", "marca": "Marca Prueba", "color": "Rojo", "placa": "ABC-123", "caracteristicas": "Toldo azul"}


def create_case(actor: Actor, slug: str = "robo-vehiculos", fields: dict | None = None, **extra) -> dict:
    body = {
        "category_id": category_id(actor, slug),
        "title": "Expediente de prueba automatizada",
        "description": "Descripción suficientemente larga del incidente ficticio de prueba.",
        "incident_at": "2026-11-01T21:30:00-05:00",
        "zone": "Zona Norte",
        "private_lat": -15.4990,
        "private_lon": -70.1330,
        "private_location_note": "Jirón Ficticio 123",
        "specific_fields": VEHICLE_FIELDS if fields is None else fields,
    }
    body.update(extra)
    r = actor.post("/api/cases", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def upload_doc(actor: Actor, case_id: int, doc_type: str, content: bytes | None = None, name: str = "doc.pdf"):
    content = content or pdf_bytes(doc_type)
    return actor.post(f"/api/cases/{case_id}/documents", data={"doc_type": doc_type, "description": "prueba"},
                      files={"file": (name, content, "application/octet-stream")})


@pytest.fixture
def flow(clean_scanner):
    """Escenario base: denunciante con expediente vehicular aprobado y publicado, revisor asignado."""
    rev = make_staff("revisor@prueba.test", Role.REVISOR, restricted=True, name="Revisor Prueba")
    rep = register("denunciante@prueba.test", "DENUNCIANTE", "Denunciante Prueba")
    case = create_case(rep)
    assert upload_doc(rep, case["id"], "DOCUMENTO_PROPIEDAD").status_code == 201
    assert upload_doc(rep, case["id"], "DECLARACION_JURADA", pdf_bytes("dj")).status_code == 201
    r = rep.post(f"/api/cases/{case['id']}/submit")
    assert r.status_code == 200, r.text
    detail = rev.get(f"/api/review/cases/{case['id']}").json()
    for d in detail["documents"]:
        assert rev.post(f"/api/review/documents/{d['id']}/assessment", json={"status": "ACEPTADO", "note": ""}).status_code == 200
    assert rev.post(f"/api/review/cases/{case['id']}/decision", json={"decision": "APROBAR", "reason": "Documentación conforme"}).status_code == 200
    r = rev.post(f"/api/review/cases/{case['id']}/publication",
                 json={"public_title": "Mototaxi roja sustraída", "public_summary": "Se busca información sobre una mototaxi roja sustraída en la Zona Norte.",
                       "public_field_keys": ["tipo_vehiculo", "color"]})
    assert r.status_code == 200, r.text
    assert rev.post(f"/api/review/cases/{case['id']}/contributions-open", json={"open": True}).status_code == 200
    return {"rev": rev, "rep": rep, "case": rev.get(f"/api/review/cases/{case['id']}").json()}


def contribute(actor: Actor, case_code: str, ctype: str = "FOTO", content: bytes | None = None, name: str = "foto.png", **form):
    data = {"case_code": case_code, "ctype": ctype, "description": form.pop("description", "Observé un vehículo similar en la avenida."),
            "certainty": form.pop("certainty", "MEDIA")}
    data.update({k: str(v) for k, v in form.items() if v is not None})
    files = None
    if ctype != "TEXTO":
        files = {"file": (name, content if content is not None else png_bytes(), "application/octet-stream")}
    return actor.post("/api/contributions", data=data, files=files)
