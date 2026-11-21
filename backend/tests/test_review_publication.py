from app.models import Role
from conftest import Actor, create_case, make_staff, pdf_bytes, register, upload_doc


def _submitted(rep, rev_needed=True):
    case = create_case(rep)
    upload_doc(rep, case["id"], "DOCUMENTO_PROPIEDAD")
    upload_doc(rep, case["id"], "DENUNCIA_POLICIAL", pdf_bytes("denuncia"))
    r = rep.post(f"/api/cases/{case['id']}/submit")
    assert r.status_code == 200, r.text
    return r.json()


def test_envio_exige_documentacion_segun_politica(clean_scanner):
    make_staff("rev@prueba.test", Role.REVISOR)
    rep = register("rep@prueba.test")
    case = create_case(rep)
    r = rep.post(f"/api/cases/{case['id']}/submit")
    assert r.status_code == 422
    assert r.json()["detail"]["problems"]
    upload_doc(rep, case["id"], "DECLARACION_JURADA")
    r = rep.post(f"/api/cases/{case['id']}/submit")
    assert r.status_code == 422  # falta documento de propiedad (política de robo vehicular)
    upload_doc(rep, case["id"], "DOCUMENTO_PROPIEDAD", pdf_bytes("propiedad"))
    r = rep.post(f"/api/cases/{case['id']}/submit")
    assert r.status_code == 200
    assert r.json()["status"] == "PENDIENTE_REVISION"
    assert r.json()["responsible"] == "Equipo de revisión"  # se asignó automáticamente


def test_documentos_no_aceptados_si_no_superan_validacion():
    """Sin antivirus operativo los documentos quedan bloqueados y no pueden aceptarse."""
    rev = make_staff("rev@prueba.test", Role.REVISOR)
    rep = register("rep@prueba.test")
    case = _submitted(rep)
    detail = rev.get(f"/api/review/cases/{case['id']}").json()
    doc = detail["documents"][0]
    assert doc["file"]["status"] == "BLOQUEADO_SIN_ANTIVIRUS"
    r = rev.post(f"/api/review/documents/{doc['id']}/assessment", json={"status": "ACEPTADO", "note": ""})
    assert r.status_code == 409
    r = rev.post(f"/api/review/cases/{case['id']}/decision", json={"decision": "APROBAR", "reason": "Intento sin examinar"})
    assert r.status_code == 422


def test_revisor_aprueba_rechaza_y_solicita_correccion(clean_scanner):
    rev = make_staff("rev@prueba.test", Role.REVISOR)
    rep = register("rep@prueba.test")
    # Solicitar corrección -> reenviar -> aprobar
    case = _submitted(rep)
    r = rev.post(f"/api/review/cases/{case['id']}/decision", json={"decision": "SOLICITAR_CORRECCION", "reason": "Adjunte documento legible"})
    assert r.json()["status"] == "CORRECCION_SOLICITADA"
    mine = rep.get(f"/api/cases/{case['id']}").json()
    assert mine["status_reason"] == "Adjunte documento legible"
    assert rep.patch(f"/api/cases/{case['id']}", json={"title": "Título corregido del expediente"}).status_code == 200
    assert rep.post(f"/api/cases/{case['id']}/submit").json()["status"] == "PENDIENTE_REVISION"
    detail = rev.get(f"/api/review/cases/{case['id']}").json()
    rev.post(f"/api/review/documents/{detail['documents'][0]['id']}/assessment", json={"status": "ACEPTADO", "note": ""})
    r = rev.post(f"/api/review/cases/{case['id']}/decision", json={"decision": "APROBAR", "reason": "Documentación conforme"})
    assert r.status_code == 200 and r.json()["status"] == "APROBADO"
    assert [d["decision"] for d in r.json()["decisions"]] == ["SOLICITAR_CORRECCION", "APROBAR"]
    # Ya aprobado no puede editarse
    assert rep.patch(f"/api/cases/{case['id']}", json={"title": "Otro título distinto"}).status_code == 409
    # Rechazo de otro expediente con motivo obligatorio
    case2 = _submitted(rep)
    assert rev.post(f"/api/review/cases/{case2['id']}/decision", json={"decision": "RECHAZAR", "reason": ""}).status_code == 422
    r = rev.post(f"/api/review/cases/{case2['id']}/decision", json={"decision": "RECHAZAR", "reason": "Documentación insuficiente"})
    assert r.json()["status"] == "RECHAZADO"
    notes = [n["title"] for n in rep.get("/api/me/notifications").json()]
    assert any("Rechazado" in t for t in notes)


def test_ficha_publica_solo_muestra_datos_autorizados(flow):
    code = flow["case"]["code"]
    pub = Actor().get(f"/api/public/cases/{code}").json()
    assert pub["public_fields"] == {"Tipo de vehículo": "Mototaxi", "Color": "Rojo"}
    text = str(pub)
    for secret in ("Jirón Ficticio", "ABC-123", "-15.499", "Denunciante Prueba", "denunciante@prueba.test", "Marca Prueba", "Descripción suficientemente"):
        assert secret not in text
    assert "documents" not in pub and "private_lat" not in pub
    listing = Actor().get("/api/public/cases").json()
    assert [c["code"] for c in listing] == [code]
    # Expedientes no publicados no aparecen
    assert Actor().get("/api/public/cases/RJ-2026-99999").status_code == 404


def test_minimizacion_rechaza_datos_personales_en_ficha(clean_scanner):
    rev = make_staff("rev@prueba.test", Role.REVISOR)
    rep = register("rep@prueba.test", name="Nombre Secreto")
    case = _submitted(rep)
    d = rev.get(f"/api/review/cases/{case['id']}").json()
    rev.post(f"/api/review/documents/{d['documents'][0]['id']}/assessment", json={"status": "ACEPTADO", "note": ""})
    rev.post(f"/api/review/cases/{case['id']}/decision", json={"decision": "APROBAR", "reason": "Conforme"})
    bad = rev.post(f"/api/review/cases/{case['id']}/publication",
                   json={"public_title": "Robo de mototaxi", "public_summary": "Contactar a Nombre Secreto al 987654321 o en -15.49901, -70.13301",
                         "public_field_keys": []})
    assert bad.status_code == 422
    assert len(bad.json()["detail"]["problems"]) >= 3
    r = rev.post(f"/api/review/cases/{case['id']}/publication",
                 json={"public_title": "Robo de mototaxi", "public_summary": "Se busca información de una mototaxi roja.", "public_field_keys": ["anio"]})
    assert r.status_code == 422  # el año no está marcado como publicable


def _approved(rep, rev, slug, fields, **extra):
    case = create_case(rep, slug, fields, **extra)
    upload_doc(rep, case["id"], "DENUNCIA_POLICIAL")
    assert rep.post(f"/api/cases/{case['id']}/submit").status_code == 200
    d = rev.get(f"/api/review/cases/{case['id']}").json()
    rev.post(f"/api/review/documents/{d['documents'][0]['id']}/assessment", json={"status": "ACEPTADO", "note": ""})
    assert rev.post(f"/api/review/cases/{case['id']}/decision", json={"decision": "APROBAR", "reason": "Conforme"}).status_code == 200
    return case


def test_restringido_requiere_doble_aprobacion_y_ficha_minima(clean_scanner):
    rev1 = make_staff("rev1@prueba.test", Role.REVISOR, restricted=True)
    rev2 = make_staff("rev2@prueba.test", Role.REVISOR, restricted=True)
    admin = make_staff("admin@prueba.test", Role.ADMIN)
    rep = register("rep@prueba.test")
    case = _approved(rep, rev1, "desaparecidas-adulto", {"edad_aproximada": 40, "ultimo_lugar": "Paradero ficticio"})
    assert case["sensitivity"] == "RESTRINGIDO"
    admin.post(f"/api/admin/cases/{case['id']}/assignments", json={"reviewer_id": rev2.user["id"]})
    body = {"public_title": "Se busca información", "public_summary": "Persona adulta no ubicada desde la tarde en zona ficticia.", "public_field_keys": ["edad_aproximada"]}
    assert rev1.post(f"/api/review/cases/{case['id']}/publication", json=body).status_code == 422  # sin campos específicos
    body["public_field_keys"] = []
    r = rev1.post(f"/api/review/cases/{case['id']}/publication", json=body)
    assert r.json()["publication_status"] == "PENDIENTE_SEGUNDA_APROBACION"
    assert Actor().get(f"/api/public/cases/{case['code']}").status_code == 404
    assert rev1.post(f"/api/review/cases/{case['id']}/publication/confirm").status_code == 409  # mismo revisor
    assert rev2.post(f"/api/review/cases/{case['id']}/publication/confirm").json()["publication_status"] == "PUBLICADO"
    assert Actor().get(f"/api/public/cases/{case['code']}").json()["public_fields"] == {}


def test_revisor_sin_habilitacion_no_accede_a_restringido(clean_scanner):
    plain = make_staff("plain@prueba.test", Role.REVISOR)  # sin permiso para RESTRINGIDO
    admin = make_staff("admin@prueba.test", Role.ADMIN)
    rep = register("rep@prueba.test")
    case = create_case(rep, "agresiones-altercados", {"descripcion_objetiva": "Discusión", "lugar": "Plaza ficticia"})
    upload_doc(rep, case["id"], "DECLARACION_JURADA")
    rep.post(f"/api/cases/{case['id']}/submit")
    r = admin.post(f"/api/admin/cases/{case['id']}/assignments", json={"reviewer_id": plain.user["id"]})
    assert r.status_code == 422
    assert plain.get(f"/api/review/cases/{case['id']}").status_code == 404


def test_institucional_no_publica_ni_abre_aportaciones(clean_scanner):
    rev = make_staff("rev@prueba.test", Role.REVISOR, restricted=True, institutional=True)
    rep = register("rep@prueba.test")
    case = _approved(rep, rev, "tratamiento-institucional", {"institucion": "Institución ficticia", "descripcion_objetiva": "Hecho ficticio"})
    assert case["sensitivity"] == "INSTITUCIONAL"
    r = rev.post(f"/api/review/cases/{case['id']}/publication",
                 json={"public_title": "Intento de publicación", "public_summary": "Texto de prueba suficientemente largo.", "public_field_keys": []})
    assert r.status_code == 409
    assert rev.post(f"/api/review/cases/{case['id']}/contributions-open", json={"open": True}).status_code == 409


def test_marcadores_protegidos_fuerzan_institucional_y_no_se_eliminan(clean_scanner):
    rep = register("rep@prueba.test")
    case = create_case(rep, "objetos-extraviados", {"tipo_objeto": "Otro", "caracteristicas": "Prueba"}, sensitive_flags=["menor_vulnerable"])
    assert case["sensitivity"] == "INSTITUCIONAL"
    r = rep.patch(f"/api/cases/{case['id']}", json={"sensitive_flags": []})
    assert r.status_code == 200
    assert r.json()["sensitivity"] == "INSTITUCIONAL"
    assert [f["key"] for f in r.json()["sensitive_flags"]] == ["menor_vulnerable"]
    assert rep.post("/api/cases", json={"category_id": case["category"]["id"], "title": "x" * 6, "description": "y" * 25,
                                        "incident_at": "2026-11-01T10:00:00", "zone": "Zona Sur",
                                        "specific_fields": {"tipo_objeto": "Otro", "caracteristicas": "a"}, "sensitive_flags": ["inventado"]}).status_code == 422


def test_admin_no_puede_reducir_protecciones():
    admin = make_staff("admin@prueba.test", Role.ADMIN)
    cats = {c["slug"]: c for c in admin.get("/api/admin/categories").json()}
    inst = cats["tratamiento-institucional"]
    r = admin.patch(f"/api/admin/categories/{inst['id']}", json={"sensitivity": "GENERAL"})
    assert r.status_code == 422
    menor = next(ch for ch in cats["personas-desaparecidas"]["children"] if ch["slug"] == "desaparecidas-menor")
    assert admin.patch(f"/api/admin/categories/{menor['id']}", json={"sensitivity": "RESTRINGIDO"}).status_code == 422
    # Sí puede elevar una categoría general
    otros = cats["otros"]
    assert admin.patch(f"/api/admin/categories/{otros['id']}", json={"sensitivity": "RESTRINGIDO"}).json()["sensitivity"] == "RESTRINGIDO"


def test_elevar_sensibilidad_retira_publicacion_existente(flow):
    admin = make_staff("admin@prueba.test", Role.ADMIN)
    cats = {c["slug"]: c for c in admin.get("/api/admin/categories").json()}
    r = admin.patch(f"/api/admin/categories/{cats['robo-vehiculos']['id']}", json={"sensitivity": "INSTITUCIONAL"})
    assert r.status_code == 200 and r.json()["upgraded_cases"] == 1
    assert Actor().get(f"/api/public/cases/{flow['case']['code']}").status_code == 404


def test_admin_edita_esquema_validado():
    admin = make_staff("admin@prueba.test", Role.ADMIN)
    cats = {c["slug"]: c for c in admin.get("/api/admin/categories").json()}
    cid = cats["otros"]["id"]
    bad = admin.patch(f"/api/admin/categories/{cid}", json={"field_schema": [{"key": "Mal Clave", "label": "x", "type": "text"}]})
    assert bad.status_code == 422
    bad = admin.patch(f"/api/admin/categories/{cid}", json={"field_schema": [{"key": "opcion", "label": "x", "type": "select"}]})
    assert bad.status_code == 422
    ok = admin.patch(f"/api/admin/categories/{cid}", json={"field_schema": [
        {"key": "tipo_descrito", "label": "Tipo", "type": "text", "required": True, "public": True},
        {"key": "testigos", "label": "¿Hubo testigos?", "type": "boolean"}]})
    assert ok.status_code == 200
    public = {c["slug"]: c for c in Actor().get("/api/categories").json()}
    assert [f["key"] for f in public["otros"]["field_schema"]] == ["tipo_descrito", "testigos"]
