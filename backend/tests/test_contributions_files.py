from pathlib import Path

from app.models import Role
from app.services import antivirus
from conftest import Actor, InfectedTestScanner, contribute, make_staff, pdf_bytes, png_bytes, register


def test_aportacion_pasa_por_cuarentena_y_validacion(flow):
    col = register("col@prueba.test", "COLABORADOR")
    r = contribute(col, flow["case"]["code"], "FOTO", declared_at="2026-11-01T21:50:00", declared_lat=-15.4950, declared_lon=-70.1320)
    assert r.status_code == 201, r.text
    c = r.json()
    assert c["status"] == "PENDIENTE_REVISION"
    f = c["file"]
    assert f["status"] == "DISPONIBLE" and len(f["sha256"]) == 64 and f["has_playback"]
    assert f["scan_engine"].startswith("DOBLE-DE-PRUEBA")
    # El colaborador consulta su estado privadamente, pero no descarga archivos
    mine = col.get("/api/contributions/mine").json()
    assert [m["code"] for m in mine] == [c["code"]]
    assert col.get(f"/api/files/{f['id']}/content").status_code == 404


def test_sin_antivirus_el_archivo_queda_bloqueado(flow):
    antivirus.set_scanner_override(None)  # motor configurado: none
    col = register("col@prueba.test", "COLABORADOR")
    c = contribute(col, flow["case"]["code"]).json()
    assert c["status"] == "BLOQUEADA"
    assert c["file"]["status"] == "BLOQUEADO_SIN_ANTIVIRUS"
    rev = flow["rev"]
    assert rev.get(f"/api/files/{c['file']['id']}/content").status_code == 409
    assert rev.post(f"/api/review/contributions/{c['id']}/classify", json={"classification": "RELEVANTE", "observation": "intento"}).status_code == 409
    # El archivo sigue en cuarentena, nunca en el almacén
    from app.config import get_settings

    root = Path(get_settings().storage_dir)
    assert len(list((root / "quarantine").iterdir())) == 1


def test_archivo_infectado_se_elimina(flow):
    antivirus.set_scanner_override(InfectedTestScanner())
    col = register("col@prueba.test", "COLABORADOR")
    c = contribute(col, flow["case"]["code"]).json()
    assert c["file"]["status"] == "INFECTADO" and c["status"] == "BLOQUEADA"
    from app.config import get_settings

    assert not list((Path(get_settings().storage_dir) / "quarantine").iterdir())


def test_validacion_de_formato_y_contenido(flow):
    col = register("col@prueba.test", "COLABORADOR")
    code = flow["case"]["code"]
    # Ejecutable disfrazado de imagen
    r = contribute(col, code, "FOTO", content=b"MZ\x90\x00" + b"\x00" * 200, name="foto.jpg")
    assert r.status_code == 415
    # PDF enviado como FOTO
    assert contribute(col, code, "FOTO", content=pdf_bytes(), name="x.png").status_code == 415
    # PDF con JavaScript embebido -> rechazado tras análisis
    evil = b"%PDF-1.4\n1 0 obj << /OpenAction << /JS (app.alert(1)) >> >> endobj\n%%EOF\n"
    r = contribute(col, code, "DOCUMENTO", content=evil, name="doc.pdf")
    assert r.status_code == 201 and r.json()["file"]["status"] == "RECHAZADO_FORMATO"
    # Imagen corrupta (firma PNG válida, contenido roto)
    r = contribute(col, code, "FOTO", content=b"\x89PNG\r\n\x1a\n" + b"basura" * 50)
    assert r.json()["file"]["status"] == "RECHAZADO_FORMATO"
    # Archivo vacío y texto con archivo
    assert contribute(col, code, "FOTO", content=b"").status_code == 422
    assert col.post("/api/contributions", data={"case_code": code, "ctype": "TEXTO", "description": "Texto con archivo adjunto", "certainty": "BAJA"},
                    files={"file": ("a.png", png_bytes(), "image/png")}).status_code == 422


def test_limite_de_tamano(flow):
    col = register("col@prueba.test", "COLABORADOR")
    big = png_bytes(size=(1600, 1600))  # PNG simple puede ser pequeño: forzamos tamaño con datos extra
    big = big + b"\x00" * (1024 * 1024 + 10)
    assert contribute(col, flow["case"]["code"], "FOTO", content=big).status_code == 413


def test_nombres_internos_aleatorios_y_fuera_de_directorio_publico(flow):
    col = register("col@prueba.test", "COLABORADOR")
    contribute(col, flow["case"]["code"], "FOTO", name="..\\..\\evil.png")
    from app.config import PROJECT_DIR, get_settings

    root = Path(get_settings().storage_dir).resolve()
    vault = list((root / "vault").iterdir())
    assert all(len(p.name) == 32 and "evil" not in p.name for p in vault)
    assert (PROJECT_DIR / "frontend").resolve() not in root.parents


def test_duplicado_exacto_detectado(flow):
    col1 = register("col1@prueba.test", "COLABORADOR")
    col2 = register("col2@prueba.test", "COLABORADOR")
    img = png_bytes((1, 2, 3))
    a = contribute(col1, flow["case"]["code"], "FOTO", content=img).json()
    b = contribute(col2, flow["case"]["code"], "FOTO", content=img).json()
    assert a["file"]["sha256"] == b["file"]["sha256"]
    detail = flow["rev"].get(f"/api/review/contributions/{b['id']}").json()
    assert detail["file"]["duplicate_of_id"] == a["file"]["id"]
    assert detail["duplicate_of_code"] == a["code"]


def test_aportaciones_solo_a_expedientes_habilitados(flow):
    col = register("col@prueba.test", "COLABORADOR")
    rev = flow["rev"]
    rev.post(f"/api/review/cases/{flow['case']['id']}/contributions-open", json={"open": False})
    assert contribute(col, flow["case"]["code"], "TEXTO").status_code == 404
    assert contribute(col, "RJ-2026-99999", "TEXTO").status_code == 404
    rev.post(f"/api/review/cases/{flow['case']['id']}/contributions-open", json={"open": True})
    assert contribute(col, flow["case"]["code"], "TEXTO").status_code == 201
    # Personal no aporta como ciudadano
    assert contribute(rev, flow["case"]["code"], "TEXTO").status_code == 403


def test_revisor_ve_seudonimo_no_identidad_del_colaborador(flow):
    col = register("identidad@prueba.test", "COLABORADOR", name="Nombre Real Colaborador")
    c = contribute(col, flow["case"]["code"], "TEXTO").json()
    detail = flow["rev"].get(f"/api/review/contributions/{c['id']}").json()
    assert detail["contributor_alias"].startswith("COL-")
    assert "Nombre Real Colaborador" not in str(detail) and "identidad@prueba.test" not in str(detail)


def test_acceso_a_archivos_autorizado_y_registrado(flow):
    col = register("col@prueba.test", "COLABORADOR")
    c = contribute(col, flow["case"]["code"]).json()
    rev = flow["rev"]
    r = rev.get(f"/api/files/{c['file']['id']}/content?variant=playback")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.headers["cache-control"].startswith("no-store")
    r = rev.get(f"/api/files/{c['file']['id']}/content?variant=original")
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    admin = make_staff("admin@prueba.test", Role.ADMIN)
    assert admin.get(f"/api/files/{c['file']['id']}/content").status_code == 404  # administración técnica sin acceso
    actions = [e["action"] for e in admin.get("/api/admin/audit").json()]
    assert "FILE_DOWNLOADED" in actions and "FILE_VIEWED" in actions
    # Documentos de respaldo: nunca públicos, solo el propio denunciante y el revisor asignado
    doc_file = flow["case"]["documents"][0]["file"]["id"]
    assert Actor().get(f"/api/files/{doc_file}/content?variant=original").status_code == 401
    assert col.get(f"/api/files/{doc_file}/content?variant=original").status_code == 404
    assert flow["rep"].get(f"/api/files/{doc_file}/content?variant=original").status_code == 200
    otro = register("otro@prueba.test")
    assert otro.get(f"/api/files/{doc_file}/content?variant=original").status_code == 404
