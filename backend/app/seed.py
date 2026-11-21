"""Inicialización de la base de datos y datos FICTICIOS de demostración.

Uso:
  python -m app.seed            # migra y carga categorías (+ demo si RJ_DEMO_MODE=true y la BD está vacía)
  python -m app.seed --reset    # elimina BD y almacenamiento locales y recrea todo (solo SQLite local)

Todas las personas, expedientes, imágenes, videos y documentos son ficticios y sintéticos.
"""
from __future__ import annotations

import argparse
import hashlib
import secrets
import shutil
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .categories_data import CATEGORIES
from .config import BACKEND_DIR, PROJECT_DIR, get_settings
from .db import SessionLocal
from .models import (
    Case,
    CaseAssignment,
    CaseDecision,
    CaseEvent,
    CaseStatus,
    Category,
    Contribution,
    ContributionStatus,
    FileStatus,
    Observation,
    PublicCard,
    PublicationStatus,
    Role,
    StoredFile,
    SupportingDocument,
    User,
)
from .security import hash_password, make_alias
from .services import pipeline, storage
from .services.policies import effective_sensitivity, floor_for_slug, higher

DEMO_PASSWORD = "Demo-Juliaca-2026"
DEMO_DOMAIN = "rastrojuliaca.test"
JULIACA = (-15.4990, -70.1330)


def run_migrations() -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(cfg, "head")


def ensure_categories(db: Session) -> None:
    for order, spec in enumerate(CATEGORIES):
        parent = db.scalar(select(Category).where(Category.slug == spec["slug"]))
        floor = floor_for_slug(spec["slug"])
        if not parent:
            parent = Category(slug=spec["slug"])
            db.add(parent)
        parent.name = spec["name"]
        parent.description = spec["description"]
        parent.icon = spec["icon"]
        parent.min_sensitivity = floor
        parent.sensitivity = higher(spec["sensitivity"], floor) if parent.sensitivity is None or parent.id is None else higher(parent.sensitivity, floor)
        parent.field_schema = spec["fields"]
        parent.document_policy = spec["policy"]
        parent.sort_order = order
        db.flush()
        for i, ch in enumerate(spec["children"]):
            child = db.scalar(select(Category).where(Category.slug == ch["slug"]))
            cfloor = floor_for_slug(ch["slug"])
            if not child:
                child = Category(slug=ch["slug"], parent_id=parent.id, sensitivity=higher(ch.get("sensitivity", "GENERAL"), cfloor))
                db.add(child)
            child.name = ch["name"]
            child.description = ""
            child.icon = ch["icon"]
            child.min_sensitivity = cfloor
            child.sensitivity = higher(child.sensitivity, cfloor)
            child.field_schema = ch["fields"]
            child.document_policy = {}
            child.sort_order = i
    db.commit()


# ---------------------------------------------------------------- medios sintéticos
def _demo_media_dir() -> Path:
    d = PROJECT_DIR / "data" / "demo_media"
    d.mkdir(parents=True, exist_ok=True)
    return d


def make_demo_image(name: str, hue: tuple[int, int, int], label: str) -> Path:
    from PIL import Image, ImageDraw

    path = _demo_media_dir() / f"{name}.jpg"
    if path.exists():
        return path
    im = Image.new("RGB", (960, 640), hue)
    d = ImageDraw.Draw(im)
    for i in range(0, 960, 60):
        d.line([(i, 640), (i + 300, 300)], fill=(min(255, hue[0] + 40), min(255, hue[1] + 40), min(255, hue[2] + 40)), width=3)
    d.rectangle([60, 380, 400, 520], fill=(30, 41, 59))
    d.ellipse([90, 490, 160, 560], fill=(15, 23, 42))
    d.ellipse([300, 490, 370, 560], fill=(15, 23, 42))
    d.rectangle([0, 0, 960, 70], fill=(11, 37, 69))
    d.text((20, 20), "IMAGEN SINTETICA DE DEMOSTRACION - RASTROJULIACA", fill=(255, 255, 255))
    d.text((20, 90), label, fill=(255, 255, 255))
    im.save(path, "JPEG", quality=85)
    return path


def make_demo_video(name: str) -> Path | None:
    s = get_settings()
    ffmpeg = s.resolved_ffmpeg()
    path = _demo_media_dir() / f"{name}.mp4"
    if path.exists():
        return path
    if not ffmpeg:
        return None
    subprocess.run(
        [ffmpeg, "-nostdin", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc2=size=640x360:rate=15", "-t", "4",
         "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path)],
        check=True, timeout=120,
    )
    return path


def make_demo_pdf(name: str, title: str) -> Path:
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    path = _demo_media_dir() / f"{name}.pdf"
    if path.exists():
        return path
    c = canvas.Canvas(str(path), pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(60, 780, "DOCUMENTO FICTICIO - SOLO PARA DEMOSTRACION")
    c.setFont("Helvetica", 12)
    c.drawString(60, 750, title)
    c.drawString(60, 720, "Este documento no tiene validez legal ni corresponde a una persona real.")
    c.drawString(60, 700, "Generado automaticamente por el script de datos de RastroJuliaca.")
    c.showPage()
    c.save()
    return path


def ingest_file(db: Session, src: Path, case_id: int, purpose: str, user: User) -> StoredFile:
    """Ingresa un archivo de demostración por el mismo pipeline real (cuarentena, antivirus, validación)."""
    internal = secrets.token_hex(16)
    dest = storage.dirs()["quarantine"] / internal
    shutil.copyfile(src, dest)
    data = dest.read_bytes()
    detected = storage.detect_type(dest)
    sha = hashlib.sha256(data).hexdigest()
    dup = db.scalar(select(StoredFile).where(StoredFile.case_id == case_id, StoredFile.sha256 == sha))
    sf = StoredFile(case_id=case_id, purpose=purpose, original_name=src.name, internal_name=internal, detected_type=detected,
                    media_class=storage.TYPE_CLASS[detected], size_bytes=len(data), sha256=sha, uploaded_by=user.id,
                    status=FileStatus.CUARENTENA.value, duplicate_of_id=dup.id if dup else None)
    db.add(sf)
    db.commit()
    pipeline.process_file(sf.id)
    db.expire_all()
    return db.get(StoredFile, sf.id)


# ---------------------------------------------------------------- datos de demostración
def _user(db: Session, email: str, name: str, role: Role, **perms) -> User:
    u = User(email=f"{email}@{DEMO_DOMAIN}", full_name=name, password_hash=hash_password(DEMO_PASSWORD), role=role.value, alias="tmp", **perms)
    db.add(u)
    db.flush()
    u.alias = make_alias(u.id)
    return u


def _ev(db, case, event, detail, actor=None, visible=True, at=None):
    db.add(CaseEvent(case_id=case.id, event=event, detail=detail, actor_id=actor.id if actor else None, visible_to_reporter=visible,
                     created_at=at or datetime.now(timezone.utc)))


def seed_demo(db: Session) -> None:
    now = datetime.now(timezone.utc)
    cat = {c.slug: c for c in db.scalars(select(Category))}

    admin = _user(db, "admin", "Administración Técnica (Demo)", Role.ADMIN)
    rev1 = _user(db, "revisor1", "Ana Revisora (Demo)", Role.REVISOR, can_review_restricted=True, can_review_institutional=True)
    rev2 = _user(db, "revisor2", "Bruno Revisor (Demo)", Role.REVISOR, can_review_restricted=True)
    den1 = _user(db, "denunciante1", "Carla Denunciante (Demo)", Role.DENUNCIANTE)
    den2 = _user(db, "denunciante2", "Diego Denunciante (Demo)", Role.DENUNCIANTE)
    col1 = _user(db, "colaborador1", "Elena Colaboradora (Demo)", Role.COLABORADOR)
    col2 = _user(db, "colaborador2", "Fabián Colaborador (Demo)", Role.COLABORADOR)
    col3 = _user(db, "colaborador3", "Gabriela Colaboradora (Demo)", Role.COLABORADOR)
    db.commit()

    seq = {"n": 0}

    def mk_case(slug, reporter, title, desc, days_ago, hour, zone, fields, status, reviewers, lat=None, lon=None, note=None, flags=None):
        c = cat[slug]
        parent = c.parent
        sens = effective_sensitivity(c.sensitivity, c.min_sensitivity, parent.sensitivity if parent else None, flags or [])
        if parent:
            sens = higher(sens, parent.min_sensitivity)
        incident = (now - timedelta(days=days_ago)).replace(hour=hour, minute=15, second=0, microsecond=0)
        case = Case(code="tmp", category_id=c.id, reporter_id=reporter.id, title=title, description=desc, incident_at=incident, zone=zone,
                    private_lat=lat, private_lon=lon, private_location_note=note, specific_fields=fields, sensitive_flags=flags or [],
                    sensitivity=sens, status=status, is_demo=True, created_at=incident + timedelta(hours=3),
                    submitted_at=None if status == CaseStatus.BORRADOR.value else incident + timedelta(hours=4))
        db.add(case)
        db.flush()
        seq["n"] += 1
        case.code = f"RJ-{now.year}-{case.id:05d}"
        _ev(db, case, "CREADO", "Expediente creado como borrador privado", reporter, at=incident + timedelta(hours=3))
        if status != CaseStatus.BORRADOR.value:
            _ev(db, case, "ENVIADO", "Enviado a revisión", reporter, at=incident + timedelta(hours=4))
        for r in reviewers:
            db.add(CaseAssignment(case_id=case.id, reviewer_id=r.id))
            _ev(db, case, "ASIGNADO", f"Asignado a {r.full_name}", None, False, at=incident + timedelta(hours=4))
        db.commit()
        return case

    def add_doc(case, reporter, doc_type, src, review_status="PENDIENTE", note=None):
        sf = ingest_file(db, src, case.id, "RESPALDO", reporter)
        d = SupportingDocument(case_id=case.id, doc_type=doc_type, description="Documento ficticio de demostración", file_id=sf.id,
                               review_status=review_status if sf.status == FileStatus.DISPONIBLE.value else "PENDIENTE", review_note=note)
        db.add(d)
        db.commit()
        return d

    def decide(case, reviewer, decision, reason, status):
        case.status = status
        case.status_reason = reason
        case.decided_at = now - timedelta(hours=20)
        db.add(CaseDecision(case_id=case.id, reviewer_id=reviewer.id, decision=decision, reason=reason))
        _ev(db, case, "DECISION", f"{decision}: {reason}", reviewer, at=case.decided_at)
        db.commit()

    def publish(case, reviewer, title, summary, public_fields, second=None):
        pc = PublicCard(case_id=case.id, public_title=title, public_summary=summary, zone=case.zone,
                        incident_date=(case.incident_at - timedelta(hours=5)).date().isoformat(), public_fields=public_fields,
                        requested_by=reviewer.id)
        db.add(pc)
        if second is False:
            case.publication_status = PublicationStatus.PENDIENTE_SEGUNDA_APROBACION.value
            _ev(db, case, "PUBLICACION", "Publicación solicitada: requiere segunda aprobación (revisión reforzada)", reviewer)
        else:
            case.publication_status = PublicationStatus.PUBLICADO.value
            pc.approved_by = reviewer.id
            pc.published_at = now - timedelta(hours=18)
            case.contributions_open = True
            _ev(db, case, "PUBLICACION", "Ficha pública generalizada publicada", reviewer)
            _ev(db, case, "APORTACIONES", "Aportaciones habilitadas", reviewer)
        db.commit()

    def contribute(case, user, ctype, desc, certainty, minutes_after=None, dlat=None, dlon=None, src=None, note=None):
        declared = case.incident_at + timedelta(minutes=minutes_after) if minutes_after is not None else None
        c = Contribution(code="tmp", case_id=case.id, contributor_id=user.id, ctype=ctype, description=desc, declared_at=declared,
                         declared_lat=dlat, declared_lon=dlon, location_note=note, certainty=certainty,
                         status=ContributionStatus.PENDIENTE_REVISION.value if ctype == "TEXTO" else ContributionStatus.EN_VALIDACION.value)
        db.add(c)
        db.flush()
        c.code = f"AP-{now.year}-{c.id:05d}"
        _ev(db, case, "APORTACION_RECIBIDA", f"{c.code} ({ctype}) recibida", None, False)
        db.commit()
        if src is not None:
            sf = ingest_file(db, src, case.id, "EVIDENCIA", user)
            c = db.get(Contribution, c.id)
            c.file_id = sf.id
            c.status = ContributionStatus.PENDIENTE_REVISION.value if sf.status == FileStatus.DISPONIBLE.value else ContributionStatus.BLOQUEADA.value
            db.commit()
        return c

    def classify(c, reviewer, cls, obs):
        c.classification = cls
        c.status = ContributionStatus.CLASIFICADA.value
        c.classified_by = reviewer.id
        c.classified_at = now - timedelta(hours=2)
        db.add(Observation(case_id=c.case_id, contribution_id=c.id, author_id=reviewer.id, text=obs))
        _ev(db, c.case, "CLASIFICACION", f"{c.code}: {cls}", reviewer, False)
        db.commit()

    pdf_prop = make_demo_pdf("tarjeta_propiedad_ficticia", "Tarjeta de propiedad vehicular (ficticia)")
    pdf_dj = make_demo_pdf("declaracion_jurada_ficticia", "Declaración jurada del denunciante (ficticia)")
    pdf_const = make_demo_pdf("constancia_ficticia", "Constancia de autoridad (ficticia)")
    pdf_den = make_demo_pdf("denuncia_ficticia", "Copia de denuncia policial (ficticia)")
    img_a = make_demo_image("escena_calle_a", (71, 85, 105), "Vista de calle - camara particular (ficticia)")
    img_b = make_demo_image("escena_calle_b", (30, 64, 92), "Vista nocturna - comercio (ficticia)")
    img_c = make_demo_image("objeto_mochila", (120, 53, 15), "Mochila azul extraviada (ficticia)")
    img_d = make_demo_image("dano_fachada", (87, 83, 78), "Fachada con daños (ficticia)")
    img_e = make_demo_image("cruce_avenida", (51, 65, 85), "Cruce de avenida tras el choque (ficticia)")
    video = make_demo_video("camara_particular")

    # 1. Robo vehicular — aprobado, publicado, con aportaciones e informe
    c1 = mk_case("robo-vehiculo-estacionado", den1, "Robo de mototaxi estacionado frente a vivienda",
                 "Mototaxi estacionada durante la noche fue sustraída. Se advirtió la ausencia a primera hora. (Caso ficticio de demostración)",
                 3, 2, "Zona Norte",
                 {"tipo_vehiculo": "Mototaxi", "marca": "Marca Demo", "modelo": "MX-150", "color": "Rojo con franja blanca", "anio": 2021,
                  "placa": "DEMO-01", "caracteristicas": "Toldo azul con calcomanía de estrella en la parte posterior."},
                 CaseStatus.PENDIENTE_REVISION.value, [rev1], JULIACA[0] + 0.006, JULIACA[1] + 0.002, "Frente a vivienda ficticia, Zona Norte")
    add_doc(c1, den1, "DOCUMENTO_PROPIEDAD", pdf_prop, "ACEPTADO")
    add_doc(c1, den1, "DECLARACION_JURADA", pdf_dj, "ACEPTADO")
    decide(c1, rev1, "APROBAR", "Documentación de propiedad y declaración jurada coherentes con lo declarado.", CaseStatus.APROBADO.value)
    publish(c1, rev1, "Mototaxi roja sustraída en Zona Norte", "Se busca información sobre una mototaxi roja con franja blanca y toldo azul sustraída durante la madrugada en la Zona Norte de Juliaca.",
            {"Tipo de vehículo": "Mototaxi", "Color": "Rojo con franja blanca", "Características distintivas": "Toldo azul con calcomanía de estrella en la parte posterior."})
    a1 = contribute(c1, col1, "VIDEO" if video else "FOTO", "Mi cámara particular registró una mototaxi con toldo azul pasando a velocidad por la avenida.", "ALTA",
                    25, JULIACA[0] + 0.009, JULIACA[1] + 0.001, video or img_a, "Cámara de mi vivienda")
    a2 = contribute(c1, col2, "FOTO", "Fotografía tomada desde un comercio, se observa un vehículo similar estacionado.", "MEDIA",
                    95, JULIACA[0] + 0.018, JULIACA[1] - 0.004, img_b)
    contribute(c1, col3, "TEXTO", "Vi una mototaxi roja con toldo azul por la salida a Huancané, no recuerdo la hora exacta.", "BAJA")
    contribute(c1, col3, "FOTO", "Recibí esta imagen por un grupo vecinal; la reenvío por si sirve.", "BAJA", 300, None, None, img_b)
    contribute(c1, col2, "FOTO", "Imagen de una calle lejana, posiblemente no relacionada.", "BAJA", 60 * 20, JULIACA[0] - 0.08, JULIACA[1] + 0.05, img_a)
    db.expire_all()
    classify(db.get(Contribution, a1.id), rev1, "RELEVANTE", "Coincide el color y el toldo descritos; la hora declarada es cercana al incidente.")

    # 2. Accidente de tránsito — aprobado y publicado
    c2 = mk_case("accidentes-transito", den2, "Choque entre automóvil y motocicleta en cruce de avenida",
                 "Colisión en un cruce de avenida durante la tarde. Se requieren registros de cámaras cercanas. (Caso ficticio)",
                 5, 17, "Centro de Juliaca",
                 {"tipo_accidente": "Choque", "vehiculos_involucrados": 2, "lugar_referencia": "Cruce de avenida principal (referencia general)",
                  "heridos": True, "descripcion_hechos": "Un automóvil y una motocicleta colisionaron en la intersección."},
                 CaseStatus.PENDIENTE_REVISION.value, [rev2], JULIACA[0] + 0.001, JULIACA[1] - 0.001)
    add_doc(c2, den2, "CONSTANCIA_AUTORIDAD", pdf_const, "ACEPTADO")
    add_doc(c2, den2, "FOTOGRAFIA_RESPALDO", img_e, "ACEPTADO")
    decide(c2, rev2, "APROBAR", "Constancia y fotografía de respaldo verificadas formalmente.", CaseStatus.APROBADO.value)
    publish(c2, rev2, "Choque en cruce de avenida del Centro", "Se solicita información o registros de cámaras sobre un choque entre un automóvil y una motocicleta ocurrido por la tarde en el Centro de Juliaca.",
            {"Tipo de accidente": "Choque", "Vehículos involucrados": 2})
    contribute(c2, col1, "FOTO", "Fotografía del cruce minutos después del choque.", "ALTA", 10, JULIACA[0] + 0.0015, JULIACA[1] - 0.0012, img_e)

    # 3. Objeto extraviado — pendiente de revisión
    c3 = mk_case("objetos-extraviados", den1, "Mochila azul extraviada en transporte público",
                 "Se extravió una mochila azul con cuadernos durante un viaje en transporte público. (Caso ficticio)",
                 1, 8, "Mercados y comercio",
                 {"tipo_objeto": "Mochila o bolso", "caracteristicas": "Mochila azul con llavero de alpaca.", "recompensa": False},
                 CaseStatus.PENDIENTE_REVISION.value, [rev2])
    add_doc(c3, den1, "FOTOGRAFIA_RESPALDO", img_c)
    add_doc(c3, den1, "DECLARACION_JURADA", pdf_dj)

    # 4. Daños materiales — corrección solicitada
    c4 = mk_case("danos-propiedad", den2, "Pintas y rotura de ventana en fachada de comercio",
                 "Durante la madrugada se rompió una ventana y se realizaron pintas en la fachada. (Caso ficticio)",
                 6, 3, "Zona Sur",
                 {"tipo_bien": "Comercio", "descripcion_danos": "Ventana rota y pintas en la fachada.", "costo_estimado": 800},
                 CaseStatus.PENDIENTE_REVISION.value, [rev1], JULIACA[0] - 0.012, JULIACA[1] + 0.004)
    add_doc(c4, den2, "FOTOGRAFIA_RESPALDO", img_d, "OBSERVADO", "La fotografía no permite identificar el inmueble; adjunte declaración jurada.")
    decide(c4, rev1, "SOLICITAR_CORRECCION", "Adjunte una declaración jurada o constancia que respalde la titularidad del comercio.",
           CaseStatus.CORRECCION_SOLICITADA.value)

    # 5. Seguridad ciudadana — aprobado, no publicado (para demostrar publicación en vivo)
    c5 = mk_case("seguridad-ciudadana", den1, "Vandalismo recurrente en parque vecinal",
                 "Se reportan daños recurrentes al mobiliario de un parque vecinal durante fines de semana. (Caso ficticio)",
                 2, 22, "Zona Este",
                 {"tipo_incidente": "Vandalismo", "recurrencia": "Frecuente", "descripcion": "Bancas y luminarias dañadas."},
                 CaseStatus.PENDIENTE_REVISION.value, [rev1], JULIACA[0] - 0.002, JULIACA[1] + 0.015)
    add_doc(c5, den1, "FOTOGRAFIA_RESPALDO", img_d, "ACEPTADO")
    decide(c5, rev1, "APROBAR", "Fotografía de respaldo suficiente para gestión vecinal.", CaseStatus.APROBADO.value)

    # 6. Persona desaparecida adulta — RESTRINGIDO, pendiente de segunda aprobación
    c6 = mk_case("desaparecidas-adulto", den2, "Persona adulta no ubicada desde la tarde",
                 "Familiar adulto no retornó a su domicilio. Existe denuncia policial. (Caso ficticio)",
                 1, 16, "Salida a Puno", {"edad_aproximada": 45, "ultimo_lugar": "Paradero de la salida a Puno", "vestimenta": "Casaca marrón"},
                 CaseStatus.PENDIENTE_REVISION.value, [rev1, rev2])
    add_doc(c6, den2, "DENUNCIA_POLICIAL", pdf_den, "ACEPTADO")
    decide(c6, rev1, "APROBAR", "Denuncia policial verificada formalmente.", CaseStatus.APROBADO.value)
    publish(c6, rev1, "Se busca información: persona adulta en salida a Puno",
            "Se solicita información a la ciudadanía sobre una persona adulta no ubicada desde la tarde en la salida a Puno.", {}, second=False)

    # 7. Robo — rechazado
    c7 = mk_case("robo-celular", den1, "Celular sustraído en feria",
                 "Reporte sin documentación suficiente. (Caso ficticio)", 9, 11, "Mercados y comercio",
                 {"modalidad": "Descuido", "bienes_sustraidos": "Celular"}, CaseStatus.PENDIENTE_REVISION.value, [rev2])
    add_doc(c7, den1, "OTRO", img_b, "OBSERVADO", "La imagen no guarda relación con el hecho declarado.")
    decide(c7, rev2, "RECHAZAR", "La documentación no permite evaluar la solicitud. Puede registrar un nuevo expediente con respaldo adecuado.",
           CaseStatus.RECHAZADO.value)

    # 8. Institucional — privado, sin publicación posible
    c8 = mk_case("tratamiento-institucional", den2, "Hecho grave en dependencia pública (ficticio)",
                 "Descripción ficticia para demostrar el tratamiento institucional reservado.", 4, 10, "Centro de Juliaca",
                 {"institucion": "Dependencia ficticia", "descripcion_objetiva": "Descripción ficticia de demostración."},
                 CaseStatus.PENDIENTE_REVISION.value, [rev1])
    add_doc(c8, den2, "DECLARACION_JURADA", pdf_dj)

    # Borrador del denunciante 2
    mk_case("robos-hurtos", den2, "Borrador: hurto de herramientas", "Borrador ficticio pendiente de completar con documentación.", 0, 7,
            "Zona Oeste", {"modalidad": "Descuido", "bienes_sustraidos": "Caja de herramientas"}, CaseStatus.BORRADOR.value, [])
    db.commit()


def reset_local() -> None:
    s = get_settings()
    if not s.database_url.startswith("sqlite:///"):
        sys.exit("--reset solo está permitido con SQLite local")
    db_path = Path(s.database_url.replace("sqlite:///", ""))
    data_dir = (PROJECT_DIR / "data").resolve()
    for p in (db_path, db_path.with_suffix(".db-wal"), db_path.with_suffix(".db-shm")):
        if p.exists() and data_dir in p.resolve().parents:
            p.unlink()
    root = Path(s.storage_dir).resolve()
    if root.exists() and data_dir in root.parents:
        shutil.rmtree(root)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true")
    ap.add_argument("--no-demo", action="store_true")
    args = ap.parse_args(argv)
    s = get_settings()
    if args.reset:
        from .db import engine

        engine.dispose()
        reset_local()
    Path(PROJECT_DIR / "data").mkdir(exist_ok=True)
    run_migrations()
    with SessionLocal() as db:
        ensure_categories(db)
        empty = db.scalar(select(User.id).limit(1)) is None
        if s.demo_mode and not args.no_demo and empty:
            print("Cargando datos FICTICIOS de demostración (incluye análisis antivirus real de cada archivo)...")
            seed_demo(db)
            blocked = db.scalars(select(StoredFile).where(StoredFile.status != FileStatus.DISPONIBLE.value)).all()
            if blocked:
                print(f"AVISO: {len(blocked)} archivo(s) de demostración no quedaron disponibles (p. ej. sin antivirus operativo): permanecen bloqueados.")
        print("Base de datos lista.")


if __name__ == "__main__":
    main()
