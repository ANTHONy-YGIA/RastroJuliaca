import pytest

from app.services.forms import FieldValidationError, validate_fields
from conftest import Actor, category_id, create_case, register

EXPECTED = {
    "robo-vehiculos", "robos-hurtos", "asaltos", "accidentes-transito", "agresiones-altercados", "danos-propiedad",
    "objetos-extraviados", "seguridad-ciudadana", "personas-desaparecidas", "tratamiento-institucional", "otros",
}


def test_catalogo_de_categorias_y_subcategorias():
    cats = Actor().get("/api/categories").json()
    assert {c["slug"] for c in cats} == EXPECTED
    by = {c["slug"]: c for c in cats}
    assert {ch["slug"] for ch in by["personas-desaparecidas"]["children"]} >= {"desaparecidas-menor", "desaparecidas-alto-riesgo"}
    # cada categoría expone su propio esquema
    keys = {f["key"] for f in by["robo-vehiculos"]["field_schema"]}
    assert {"marca", "modelo", "color", "caracteristicas"} <= keys
    assert {f["key"] for f in by["accidentes-transito"]["field_schema"]} >= {"tipo_accidente", "lugar_referencia"}
    assert {f["key"] for f in by["objetos-extraviados"]["field_schema"]} >= {"tipo_objeto", "caracteristicas"}
    assert by["tratamiento-institucional"]["sensitivity"] == "INSTITUCIONAL"


def test_subcategoria_hereda_campos_y_agrega_propios():
    cats = {c["slug"]: c for c in Actor().get("/api/categories").json()}
    autopartes = next(ch for ch in cats["robo-vehiculos"]["children"] if ch["slug"] == "robo-autopartes")
    keys = [f["key"] for f in autopartes["field_schema"]]
    assert "marca" in keys and "autopartes" in keys
    menor = next(ch for ch in cats["personas-desaparecidas"]["children"] if ch["slug"] == "desaparecidas-menor")
    assert menor["sensitivity"] == "INSTITUCIONAL"


SCHEMA = [
    {"key": "tipo", "label": "Tipo", "type": "select", "required": True, "options": ["A", "B"]},
    {"key": "placa", "label": "Placa", "type": "text", "pattern": r"^[A-Z0-9-]{3,8}$"},
    {"key": "num", "label": "N", "type": "number", "min": 1, "max": 5},
    {"key": "fecha", "label": "F", "type": "date"},
    {"key": "flag", "label": "B", "type": "boolean"},
]


def test_validacion_de_campos_dinamicos():
    assert validate_fields(SCHEMA, {"tipo": "A", "placa": "ABC-123", "num": "3", "fecha": "2026-01-05", "flag": True}) == {
        "tipo": "A", "placa": "ABC-123", "num": 3, "fecha": "2026-01-05", "flag": True}
    with pytest.raises(FieldValidationError) as e:
        validate_fields(SCHEMA, {"placa": "abc 123", "num": 9, "fecha": "05/01/2026", "flag": "si", "extra": "x"})
    errs = e.value.errors
    assert set(errs) == {"tipo", "placa", "num", "fecha", "flag", "extra"}
    with pytest.raises(FieldValidationError):
        validate_fields(SCHEMA, {"tipo": "C"})


def test_creacion_de_distintas_categorias():
    rep = register("multi@prueba.test")
    c1 = create_case(rep, "robo-vehiculos")
    assert c1["category"]["slug"] == "robo-vehiculos" and c1["specific_fields"]["marca"] == "Marca Prueba"
    c2 = create_case(rep, "accidentes-transito", {"tipo_accidente": "Choque", "lugar_referencia": "Cruce ficticio", "descripcion_hechos": "Choque de prueba"})
    assert c2["specific_fields"]["tipo_accidente"] == "Choque"
    c3 = create_case(rep, "objetos-extraviados", {"tipo_objeto": "Llaves", "caracteristicas": "Llavero rojo"})
    assert c3["status"] == "BORRADOR" and c3["sensitivity"] == "GENERAL"
    c4 = create_case(rep, "agresiones-altercados", {"descripcion_objetiva": "Discusión en la vía pública", "lugar": "Plaza ficticia"})
    assert c4["sensitivity"] == "RESTRINGIDO"
    codes = {c["code"] for c in rep.get("/api/cases/mine").json()}
    assert {c1["code"], c2["code"], c3["code"], c4["code"]} == codes


def test_backend_rechaza_campos_de_otra_categoria():
    rep = register("campos@prueba.test")
    r = rep.post("/api/cases", json={
        "category_id": category_id(rep, "accidentes-transito"), "title": "Accidente de prueba", "description": "Descripción larga del accidente ficticio",
        "incident_at": "2026-11-01T10:00:00", "zone": "Zona Sur",
        "specific_fields": {"marca": "Toyota", "tipo_accidente": "Choque"},  # falta obligatorio + campo ajeno
    })
    assert r.status_code == 422
    fields = r.json()["detail"]["fields"]
    assert "marca" in fields and "lugar_referencia" in fields


def test_validaciones_generales_del_expediente():
    rep = register("val@prueba.test")
    base = {"category_id": category_id(rep, "otros"), "title": "Título válido", "description": "Descripción suficientemente extensa.",
            "zone": "Zona Sur", "specific_fields": {"tipo_descrito": "Prueba"}}
    assert rep.post("/api/cases", json=base | {"incident_at": "2099-01-01T00:00:00"}).status_code == 422  # futuro
    assert rep.post("/api/cases", json=base | {"incident_at": "2026-11-01T00:00:00", "zone": "Lima"}).status_code == 422
    assert rep.post("/api/cases", json=base | {"incident_at": "2026-11-01T00:00:00", "private_lat": -15.5}).status_code == 422
    assert rep.post("/api/cases", json=base | {"incident_at": "2026-11-01T00:00:00"}).status_code == 201


def test_colaborador_no_crea_expedientes():
    col = register("col@prueba.test", "COLABORADOR")
    r = col.post("/api/cases", json={"category_id": 1})
    assert r.status_code in (403, 422)
    assert col.get("/api/cases/mine").status_code == 403
