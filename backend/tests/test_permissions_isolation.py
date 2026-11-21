from app.models import Role
from conftest import Actor, contribute, create_case, make_staff, register


def test_denunciante_no_accede_a_expedientes_ajenos(flow):
    otro = register("otro@prueba.test")
    cid = flow["case"]["id"]
    assert otro.get(f"/api/cases/{cid}").status_code == 404
    assert otro.patch(f"/api/cases/{cid}", json={"title": "Intento de modificación"}).status_code == 404
    assert otro.post(f"/api/cases/{cid}/submit").status_code == 404
    assert otro.post(f"/api/cases/{cid}/documents", data={"doc_type": "OTRO"}, files={"file": ("a.pdf", b"%PDF-1.4\n%%EOF", "application/pdf")}).status_code == 404


def test_revisor_no_asignado_no_accede(flow):
    ajeno = make_staff("ajeno@prueba.test", Role.REVISOR, restricted=True, institutional=True)
    cid = flow["case"]["id"]
    for url in (f"/api/review/cases/{cid}", f"/api/review/cases/{cid}/contributions", f"/api/review/cases/{cid}/timeline"):
        assert ajeno.get(url).status_code == 404
    assert ajeno.post(f"/api/review/cases/{cid}/decision", json={"decision": "CERRAR", "reason": "intento ajeno"}).status_code == 404
    doc_file = flow["case"]["documents"][0]["file"]["id"]
    assert ajeno.get(f"/api/files/{doc_file}/content").status_code == 404
    assert ajeno.get("/api/review/cases").json() == []


def test_roles_no_cruzan_permisos(flow):
    col = register("col@prueba.test", "COLABORADOR")
    rep = flow["rep"]
    admin = make_staff("admin@prueba.test", Role.ADMIN)
    rev = flow["rev"]
    assert col.get("/api/review/dashboard").status_code == 403
    assert rep.get("/api/review/cases").status_code == 403
    assert rep.get("/api/admin/users").status_code == 403
    assert rev.get("/api/admin/users").status_code == 403
    # La administración técnica no examina expedientes ni evidencias
    assert admin.get(f"/api/review/cases/{flow['case']['id']}").status_code == 403
    assert admin.get(f"/api/cases/{flow['case']['id']}").status_code == 403
    admin_view = admin.get("/api/admin/cases").json()
    assert "description" not in admin_view[0] and "title" not in admin_view[0]


def test_aislamiento_entre_expedientes(flow, clean_scanner):
    rev, rep = flow["rev"], flow["rep"]
    # Segundo expediente publicado por el mismo revisor
    from conftest import pdf_bytes, upload_doc

    case2 = create_case(rep, "accidentes-transito", {"tipo_accidente": "Choque", "lugar_referencia": "Cruce", "descripcion_hechos": "Choque"})
    upload_doc(rep, case2["id"], "CONSTANCIA_AUTORIDAD", pdf_bytes("c2"))
    rep.post(f"/api/cases/{case2['id']}/submit")
    d = rev.get(f"/api/review/cases/{case2['id']}").json()
    rev.post(f"/api/review/documents/{d['documents'][0]['id']}/assessment", json={"status": "ACEPTADO", "note": ""})
    rev.post(f"/api/review/cases/{case2['id']}/decision", json={"decision": "APROBAR", "reason": "Conforme"})
    rev.post(f"/api/review/cases/{case2['id']}/publication", json={"public_title": "Choque en cruce", "public_summary": "Se busca información de un choque ficticio.", "public_field_keys": []})
    rev.post(f"/api/review/cases/{case2['id']}/contributions-open", json={"open": True})

    col = register("col@prueba.test", "COLABORADOR")
    a1 = contribute(col, flow["case"]["code"], "TEXTO").json()
    a2 = contribute(col, d["code"], "TEXTO", description="Información del choque en el cruce.").json()
    items1 = rev.get(f"/api/review/cases/{flow['case']['id']}/contributions").json()["items"]
    items2 = rev.get(f"/api/review/cases/{case2['id']}/contributions").json()["items"]
    assert [i["code"] for i in items1] == [a1["code"]]
    assert [i["code"] for i in items2] == [a2["code"]]
    # Un informe no puede mezclar evidencias de otro expediente
    r = rev.post(f"/api/review/cases/{flow['case']['id']}/reports",
                 json={"title": "Informe mixto", "summary": "Intento de mezclar evidencias de dos expedientes.", "contribution_ids": [a1["id"], a2["id"]]})
    assert r.status_code == 422
    # Un colaborador no ve aportaciones ajenas
    otro = register("otro@prueba.test", "COLABORADOR")
    assert otro.get(f"/api/contributions/{a1['id']}").status_code == 404


def test_idor_en_notificaciones_y_solicitudes():
    a = register("a@prueba.test")
    b = register("b@prueba.test")
    make_staff("admin@prueba.test", Role.ADMIN)
    a.post("/api/me/data-requests", json={"rtype": "ACCESO", "detail": "Solicito copia de mis datos personales"})
    admin_notifs = Actor().login("admin@prueba.test").get("/api/me/notifications").json()
    assert admin_notifs
    assert b.post(f"/api/me/notifications/{admin_notifs[0]['id']}/read").status_code == 404
    assert b.get("/api/me/data-requests").json() == []
