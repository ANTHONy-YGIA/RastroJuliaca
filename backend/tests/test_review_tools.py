import hashlib
import json

from app.routers.reports import canonical
from app.services.geo import haversine_km
from conftest import contribute, register


def _seed_contribs(flow):
    code = flow["case"]["code"]
    col = register("col@prueba.test", "COLABORADOR")
    near = contribute(col, code, "FOTO", declared_at="2026-11-01T21:45:00", declared_lat=-15.4995, declared_lon=-70.1335).json()
    far = contribute(col, code, "FOTO", content=None, declared_at="2026-11-01T23:30:00", declared_lat=-15.5800, declared_lon=-70.1000,
                     description="Fotografía tomada lejos del lugar.").json()
    nodata = contribute(col, code, "TEXTO", description="Lo vi pero no recuerdo hora ni lugar exacto.").json()
    mid = contribute(col, code, "TEXTO", declared_at="2026-11-01T22:10:00", declared_lat=-15.5100, declared_lon=-70.1300,
                     description="Vehículo similar visto en la avenida.").json()
    return col, near, far, nodata, mid


def test_haversine():
    # Juliaca - Puno ~ 33-34 km en línea recta
    d = haversine_km(-15.4990, -70.1330, -15.8402, -70.0219)
    assert 35 < d < 40
    assert haversine_km(0, 0, 0, 0) == 0


def test_ordenamiento_por_proximidad_y_datos_insuficientes(flow):
    _, near, far, nodata, mid = _seed_contribs(flow)
    rev, cid = flow["rev"], flow["case"]["id"]
    res = rev.get(f"/api/review/cases/{cid}/contributions?sort=distance").json()
    assert [i["code"] for i in res["items"]] == [near["code"], mid["code"], far["code"], nodata["code"]]
    assert res["items"][0]["distance_km"] < 0.2
    assert res["items"][-1]["distance_km"] is None
    assert any("insuficientes" in n for n in res["items"][-1]["data_quality"])
    res = rev.get(f"/api/review/cases/{cid}/contributions?sort=time").json()
    assert [i["code"] for i in res["items"]][:3] == [near["code"], mid["code"], far["code"]]


def test_filtro_por_radio_no_descarta_sin_datos(flow):
    _, near, far, nodata, mid = _seed_contribs(flow)
    rev, cid = flow["rev"], flow["case"]["id"]
    res = rev.get(f"/api/review/cases/{cid}/contributions?max_km=3").json()
    codes = {i["code"] for i in res["items"]}
    assert far["code"] not in codes
    assert {near["code"], mid["code"], nodata["code"]} <= codes  # sin coordenadas: se conserva
    assert res["hidden_by_filters"] == 1
    res = rev.get(f"/api/review/cases/{cid}/contributions?ctype=TEXTO").json()
    assert {i["code"] for i in res["items"]} == {nodata["code"], mid["code"]}


def test_clasificacion_y_observaciones(flow):
    _, near, far, *_ = _seed_contribs(flow)
    rev = flow["rev"]
    r = rev.post(f"/api/review/contributions/{near['id']}/classify", json={"classification": "RELEVANTE", "observation": "Coincide con la descripción"})
    assert r.status_code == 200
    assert r.json()["classification"] == "RELEVANTE" and r.json()["status"] == "CLASIFICADA"
    assert rev.post(f"/api/review/contributions/{far['id']}/classify", json={"classification": "INVENTADA", "observation": "x"}).status_code == 422
    rev.post(f"/api/review/contributions/{near['id']}/observations", json={"text": "Solicitar original al colaborador"})
    detail = rev.get(f"/api/review/contributions/{near['id']}").json()
    assert [o["text"] for o in detail["observations"]] == ["Coincide con la descripción", "Solicitar original al colaborador"]
    res = rev.get(f"/api/review/cases/{flow['case']['id']}/contributions?classification=RELEVANTE").json()
    assert [i["code"] for i in res["items"]] == [near["code"]]
    dash = rev.get("/api/review/dashboard").json()
    assert dash["counts"]["evidence_classified"] == 1 and dash["counts"]["cases_approved"] == 1


def test_linea_de_tiempo_y_correcciones_sin_sobrescribir(flow):
    col, near, far, nodata, mid = _seed_contribs(flow)
    rev, cid = flow["rev"], flow["case"]["id"]
    tl = rev.get(f"/api/review/cases/{cid}/timeline").json()
    order = [e.get("code", "INCIDENTE") for e in tl["entries"]]
    assert order == ["INCIDENTE", near["code"], mid["code"], far["code"]]
    assert [u["code"] for u in tl["undated"]] == [nodata["code"]]
    assert "no constituyen hechos comprobados" in tl["notice"]
    # Corrección justificada del colaborador: el dato original se conserva
    assert col.post(f"/api/contributions/{far['id']}/corrections", json={"field": "declared_at", "new_value": "2026-11-01T21:20:00", "reason": "corto"}).status_code == 422
    r = col.post(f"/api/contributions/{far['id']}/corrections",
                 json={"field": "declared_at", "new_value": "2026-11-01T21:20:00", "reason": "Revisé el reloj de la cámara y estaba adelantado"})
    assert r.status_code == 201
    body = r.json()
    assert body["original"]["declared_at"] == "2026-11-02T04:30:00Z"
    assert body["effective"]["declared_at"] == "2026-11-02T02:20:00Z"
    tl = rev.get(f"/api/review/cases/{cid}/timeline").json()
    entry = next(e for e in tl["entries"] if e.get("code") == far["code"])
    assert entry["corrected"] and entry["original_at"] == "2026-11-02T04:30:00Z"
    assert tl["entries"][0].get("code") == far["code"]  # la hora corregida es anterior a la del incidente
    # Corrección del revisor sobre la ubicación
    r = rev.post(f"/api/review/contributions/{nodata['id']}/corrections",
                 json={"field": "declared_lat", "new_value": "-15.50", "reason": "El colaborador precisó la ubicación por teléfono"})
    assert r.json()["original"]["declared_lat"] is None and r.json()["effective"]["declared_lat"] == -15.5


def test_informe_json_con_integridad_y_auditoria(flow):
    _, near, far, *_ = _seed_contribs(flow)
    rev = flow["rev"]
    rev.post(f"/api/review/contributions/{near['id']}/classify", json={"classification": "RELEVANTE", "observation": "Coincide"})
    r = rev.post(f"/api/review/cases/{flow['case']['id']}/reports",
                 json={"title": "Informe de evidencias", "summary": "Resumen de las evidencias relevantes del expediente ficticio.",
                       "contribution_ids": [near["id"], far["id"]]})
    assert r.status_code == 201, r.text
    rep = r.json()
    content = rep["content"]
    assert content["case"]["code"] == flow["case"]["code"]
    assert [e["code"] for e in content["evidence"]] == [near["code"], far["code"]]
    assert content["evidence"][0]["file"]["sha256"] == near["file"]["sha256"]
    assert content["evidence"][0]["observations"][0]["text"] == "Coincide"
    assert "private_location" not in content["case"]  # ubicaciones privadas solo si se solicitan
    assert any(h["event"] == "DECISION" for h in content["history"])
    exp = rev.get(f"/api/reports/{rep['id']}/export.json")
    assert exp.status_code == 200 and "attachment" in exp.headers["content-disposition"]
    payload = json.loads(exp.content)
    assert hashlib.sha256(canonical(payload["report"])).hexdigest() == payload["integrity"]["content_sha256"] == rep["content_sha256"]
    pdf = rev.get(f"/api/reports/{rep['id']}/export.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert rev.get(f"/api/reports/{rep['id']}").json()["export_count"] == 2
    from app.models import Role
    from conftest import make_staff

    admin = make_staff("admin@prueba.test", Role.ADMIN)
    exports = admin.get("/api/admin/audit?action=REPORT_EXPORTED").json()
    assert len(exports) == 2 and {e["details"]["format"] for e in exports} == {"json", "pdf"}
    # Otro denunciante o revisor no asignado no accede al informe
    otro = make_staff("otro@prueba.test", Role.REVISOR)
    assert otro.get(f"/api/reports/{rep['id']}/export.json").status_code == 404
    assert flow["rep"].get(f"/api/reports/{rep['id']}").status_code == 403
