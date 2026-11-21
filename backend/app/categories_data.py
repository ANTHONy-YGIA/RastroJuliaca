"""Catálogo inicial de categorías y subcategorías con sus esquemas de campos configurables."""
from __future__ import annotations

ANY_BASIC = ["DENUNCIA_POLICIAL", "CONSTANCIA_AUTORIDAD", "DECLARACION_JURADA"]


def f(key, label, type_, required=False, public=False, **kw):
    d = {"key": key, "label": label, "type": type_, "required": required, "public": public}
    d.update(kw)
    return d


CATEGORIES = [
    {
        "slug": "robo-vehiculos", "name": "Robo de vehículos", "icon": "car",
        "description": "Sustracción de vehículos o autopartes.",
        "sensitivity": "GENERAL",
        "fields": [
            f("tipo_vehiculo", "Tipo de vehículo", "select", True, True, options=["Automóvil", "Camioneta", "Motocicleta", "Mototaxi", "Bicicleta", "Otro"]),
            f("marca", "Marca", "text", True, True, max_length=60),
            f("modelo", "Modelo", "text", False, True, max_length=60),
            f("color", "Color", "text", True, True, max_length=40),
            f("anio", "Año de fabricación", "number", False, False, min=1950, max=2027),
            f("placa", "Placa", "text", False, True, pattern=r"^[A-Z0-9-]{3,8}$", help="Mayúsculas y números, p. ej. ABC-123"),
            f("caracteristicas", "Características distintivas", "textarea", False, True, max_length=800),
        ],
        "policy": {"min_documents": 2, "required_any": [["DOCUMENTO_PROPIEDAD"], ANY_BASIC],
                   "note": "Documento de propiedad del vehículo y denuncia, constancia o declaración jurada."},
        "children": [
            {"slug": "robo-vehiculo-estacionado", "name": "Vehículo estacionado", "icon": "square-parking", "fields": []},
            {"slug": "robo-autopartes", "name": "Robo de autopartes", "icon": "wrench",
             "fields": [f("autopartes", "Autopartes sustraídas", "textarea", True, True, max_length=500)]},
        ],
    },
    {
        "slug": "robos-hurtos", "name": "Robos y hurtos", "icon": "wallet",
        "description": "Sustracción de bienes personales, en vivienda o comercio.",
        "sensitivity": "GENERAL",
        "fields": [
            f("modalidad", "Modalidad", "select", True, True, options=["Arrebato", "Descuido", "Ingreso a domicilio", "Ingreso a comercio", "Otro"]),
            f("bienes_sustraidos", "Bienes sustraídos", "textarea", True, True, max_length=800),
            f("valor_estimado", "Valor estimado (S/)", "number", False, False, min=0, max=10_000_000),
        ],
        "policy": {"min_documents": 1, "required_any": [ANY_BASIC], "note": "Denuncia, constancia o declaración jurada."},
        "children": [
            {"slug": "hurto-vivienda", "name": "Hurto en vivienda", "icon": "house", "fields": []},
            {"slug": "robo-comercio", "name": "Robo en comercio", "icon": "store", "fields": []},
            {"slug": "robo-celular", "name": "Robo de celular", "icon": "smartphone",
             "fields": [f("marca_equipo", "Marca y modelo del equipo", "text", False, True, max_length=80)]},
        ],
    },
    {
        "slug": "asaltos", "name": "Asaltos", "icon": "shield-alert",
        "description": "Robos con violencia o amenaza.",
        "sensitivity": "GENERAL",
        "fields": [
            f("numero_agresores", "Número de agresores", "number", False, True, min=1, max=20),
            f("uso_armas", "Uso de armas", "select", True, False, options=["No se observó", "Arma blanca", "Arma de fuego", "Otro", "No sabe"]),
            f("heridos", "¿Hubo personas heridas?", "boolean", False, False),
            f("bienes_sustraidos", "Bienes sustraídos", "textarea", False, True, max_length=800),
        ],
        "policy": {"min_documents": 1, "required_any": [ANY_BASIC + ["INFORME_MEDICO"]], "note": "Denuncia, constancia, declaración jurada o informe médico."},
        "children": [],
    },
    {
        "slug": "accidentes-transito", "name": "Accidentes de tránsito", "icon": "car-front",
        "description": "Choques, atropellos y otros siniestros viales.",
        "sensitivity": "GENERAL",
        "fields": [
            f("tipo_accidente", "Tipo de accidente", "select", True, True, options=["Choque", "Atropello", "Despiste", "Volcadura", "Otro"]),
            f("vehiculos_involucrados", "Vehículos involucrados", "number", False, True, min=1, max=20),
            f("lugar_referencia", "Lugar (referencia general)", "text", True, True, max_length=120),
            f("heridos", "¿Hubo personas heridas?", "boolean", False, False),
            f("descripcion_hechos", "Descripción del accidente", "textarea", True, False, max_length=1500),
        ],
        "policy": {"min_documents": 1, "required_any": [ANY_BASIC + ["FOTOGRAFIA_RESPALDO", "VIDEO_RESPALDO"]],
                   "note": "No siempre existe denuncia formal: se acepta constancia, declaración jurada o material de respaldo."},
        "children": [],
    },
    {
        "slug": "agresiones-altercados", "name": "Agresiones y altercados", "icon": "users",
        "description": "Agresiones físicas o verbales y altercados en la vía pública.",
        "sensitivity": "RESTRINGIDO",
        "fields": [
            f("descripcion_objetiva", "Descripción objetiva de los hechos", "textarea", True, False, max_length=1500,
              help="Describa hechos observables, sin juicios ni acusaciones."),
            f("lugar", "Lugar (referencia general)", "text", True, False, max_length=120),
            f("personas_involucradas", "Personas involucradas", "number", False, False, min=1, max=50),
        ],
        "policy": {"min_documents": 1, "required_any": [ANY_BASIC + ["INFORME_MEDICO"]]},
        "children": [],
    },
    {
        "slug": "danos-propiedad", "name": "Daños a la propiedad", "icon": "hammer",
        "description": "Daños materiales a viviendas, vehículos, comercios o bienes públicos.",
        "sensitivity": "GENERAL",
        "fields": [
            f("tipo_bien", "Tipo de bien afectado", "select", True, True, options=["Vivienda", "Vehículo", "Comercio", "Bien público", "Otro"]),
            f("descripcion_danos", "Descripción de los daños", "textarea", True, True, max_length=1000),
            f("costo_estimado", "Costo estimado (S/)", "number", False, False, min=0, max=10_000_000),
        ],
        "policy": {"min_documents": 1, "required_any": [ANY_BASIC + ["FOTOGRAFIA_RESPALDO", "DOCUMENTO_PROPIEDAD"]]},
        "children": [],
    },
    {
        "slug": "objetos-extraviados", "name": "Objetos extraviados", "icon": "package-search",
        "description": "Pérdida de documentos, equipos u objetos personales.",
        "sensitivity": "GENERAL",
        "fields": [
            f("tipo_objeto", "Tipo de objeto", "select", True, True, options=["Documentos", "Celular", "Billetera", "Llaves", "Mochila o bolso", "Mascota", "Otro"]),
            f("caracteristicas", "Características del objeto", "textarea", True, True, max_length=800),
            f("recompensa", "¿Ofrece recompensa?", "boolean", False, True),
        ],
        "policy": {"min_documents": 1, "required_any": [["DECLARACION_JURADA", "DOCUMENTO_PROPIEDAD", "FOTOGRAFIA_RESPALDO", "DENUNCIA_POLICIAL"]],
                   "note": "Una fotografía del objeto o comprobante de propiedad, o declaración jurada."},
        "children": [],
    },
    {
        "slug": "seguridad-ciudadana", "name": "Incidentes de seguridad ciudadana", "icon": "siren",
        "description": "Situaciones que afectan la convivencia y seguridad del vecindario.",
        "sensitivity": "GENERAL",
        "fields": [
            f("tipo_incidente", "Tipo de incidente", "select", True, True, options=["Actividad sospechosa", "Disturbio", "Vandalismo", "Consumo en vía pública", "Otro"]),
            f("recurrencia", "Recurrencia", "select", False, True, options=["Primera vez", "Ocasional", "Frecuente"]),
            f("descripcion", "Descripción", "textarea", True, False, max_length=1500),
        ],
        "policy": {"min_documents": 1, "required_any": [ANY_BASIC + ["FOTOGRAFIA_RESPALDO", "VIDEO_RESPALDO"]]},
        "children": [],
    },
    {
        "slug": "personas-desaparecidas", "name": "Personas desaparecidas", "icon": "user-search",
        "description": "Requiere denuncia o constancia de autoridad. Protección reforzada.",
        "sensitivity": "RESTRINGIDO",
        "fields": [
            f("edad_aproximada", "Edad aproximada", "number", True, False, min=0, max=120),
            f("ultimo_lugar", "Último lugar donde fue vista (referencia general)", "text", True, False, max_length=120),
            f("vestimenta", "Vestimenta", "textarea", False, False, max_length=500),
        ],
        "policy": {"min_documents": 1, "required_any": [["DENUNCIA_POLICIAL", "CONSTANCIA_AUTORIDAD"]],
                   "note": "Obligatoria la denuncia policial o constancia de autoridad."},
        "children": [
            {"slug": "desaparecidas-adulto", "name": "Persona adulta (sin indicios de alto riesgo)", "icon": "user", "fields": []},
            {"slug": "desaparecidas-menor", "name": "Menor de edad", "icon": "baby", "fields": [], "sensitivity": "INSTITUCIONAL"},
            {"slug": "desaparecidas-alto-riesgo", "name": "Alto riesgo", "icon": "triangle-alert", "fields": [], "sensitivity": "INSTITUCIONAL"},
        ],
    },
    {
        "slug": "tratamiento-institucional", "name": "Incidentes graves de tratamiento institucional", "icon": "landmark",
        "description": "Hechos graves que involucran a instituciones. Expediente privado por defecto.",
        "sensitivity": "INSTITUCIONAL",
        "fields": [
            f("institucion", "Institución involucrada", "text", True, False, max_length=120),
            f("descripcion_objetiva", "Descripción objetiva de los hechos", "textarea", True, False, max_length=2000),
        ],
        "policy": {"min_documents": 1, "required_any": [ANY_BASIC + ["INFORME_MEDICO"]]},
        "children": [],
    },
    {
        "slug": "otros", "name": "Otros", "icon": "circle-help",
        "description": "Incidentes que no corresponden a las categorías anteriores.",
        "sensitivity": "GENERAL",
        "fields": [f("tipo_descrito", "Tipo de incidente", "text", True, True, max_length=120)],
        "policy": {"min_documents": 1, "required_any": []},
        "children": [],
    },
]
