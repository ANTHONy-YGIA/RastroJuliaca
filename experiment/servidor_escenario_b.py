"""Carga un conjunto experimental en una instancia AISLADA de RastroJuliaca (escenario B) y la inicia.

  .\\scripts\\py.ps1 experiment\\servidor_escenario_b.py --conjunto C1 [--puerto 8010]

Crea una BD propia (data/experimento-<C>.db), un revisor evaluador y los 3 expedientes del conjunto
aprobados y publicados, e ingresa cada evidencia por el pipeline real (cuarentena + antivirus + hash).
Credenciales del participante: evaluador@experimento.test / Experimento-2026
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--conjunto", choices=["C1", "C2"], required=True)
    ap.add_argument("--puerto", type=int, default=8010)
    ap.add_argument("--solo-cargar", action="store_true")
    a = ap.parse_args()
    data = ROOT / "experiment" / "conjuntos" / a.conjunto
    if not (data / "aportaciones.json").exists():
        sys.exit("Ejecute primero experiment/generar_conjuntos.py")
    os.environ["RJ_DATABASE_URL"] = f"sqlite:///{(ROOT / 'data' / f'experimento-{a.conjunto}.db').as_posix()}"
    os.environ["RJ_STORAGE_DIR"] = str(ROOT / "data" / f"experimento-{a.conjunto}-storage")
    os.environ["RJ_DEMO_MODE"] = "true"

    from sqlalchemy import select

    from app.db import SessionLocal, engine
    from app.models import (Case, CaseAssignment, Category, Contribution, ContributionStatus, FileStatus, PublicCard,
                            PublicationStatus, Role, User)
    from app.security import hash_password, make_alias
    from app.seed import ensure_categories, ingest_file, reset_local, run_migrations

    engine.dispose()
    reset_local()
    (ROOT / "data").mkdir(exist_ok=True)
    run_migrations()
    spec = json.loads((data / "aportaciones.json").read_text(encoding="utf-8"))
    with SessionLocal() as db:
        ensure_categories(db)
        users = {}
        for email, name, role in [("evaluador@experimento.test", "Evaluador (Experimento)", Role.REVISOR),
                                  ("ciudadano@experimento.test", "Ciudadano ficticio", Role.DENUNCIANTE),
                                  ("aportante@experimento.test", "Aportante ficticio", Role.COLABORADOR)]:
            u = User(email=email, full_name=name, password_hash=hash_password("Experimento-2026"), role=role.value, alias="tmp")
            db.add(u)
            db.flush()
            u.alias = make_alias(u.id)
            users[role] = u
        db.commit()
        cases = {}
        for key, e in spec["expedientes"].items():
            cat = db.scalar(select(Category).where(Category.slug == e["categoria"]))
            inc = datetime.fromisoformat(e["incidente"]).replace(tzinfo=timezone(timedelta(hours=-5)))
            c = Case(code="tmp", category_id=cat.id, reporter_id=users[Role.DENUNCIANTE].id, title=e["titulo"], description=f"Expediente experimental ficticio: {e['titulo']}.",
                     incident_at=inc, zone=e["zona"], private_lat=e["lat"], private_lon=e["lon"], specific_fields={}, sensitivity=cat.sensitivity,
                     status="APROBADO", publication_status=PublicationStatus.PUBLICADO.value, contributions_open=True, is_demo=True)
            db.add(c)
            db.flush()
            c.code = f"RJ-EXP-{a.conjunto}-{key}"
            db.add(PublicCard(case_id=c.id, public_title=e["titulo"], public_summary=f"Expediente experimental ficticio ({e['zona']}).", zone=e["zona"],
                              incident_date=inc.date().isoformat(), public_fields={}, requested_by=users[Role.REVISOR].id, approved_by=users[Role.REVISOR].id,
                              published_at=datetime.now(timezone.utc)))
            db.add(CaseAssignment(case_id=c.id, reviewer_id=users[Role.REVISOR].id))
            cases[key] = c
        db.commit()
        for ap_ in spec["aportes"]:
            c = cases[ap_["expediente"]]
            contrib = Contribution(code="tmp", case_id=c.id, contributor_id=users[Role.COLABORADOR].id, ctype="FOTO", description=ap_["descripcion"],
                                   declared_at=datetime.fromisoformat(ap_["declared_at"]) if ap_["declared_at"] else None,
                                   declared_lat=ap_["lat"], declared_lon=ap_["lon"], certainty=ap_["certeza"], status=ContributionStatus.EN_VALIDACION.value)
            db.add(contrib)
            db.flush()
            contrib.code = f"AP-EXP-{a.conjunto}-{ap_['id']:02d}"
            db.commit()
            sf = ingest_file(db, data / ap_["archivo"], c.id, "EVIDENCIA", users[Role.COLABORADOR])
            contrib = db.get(Contribution, contrib.id)
            contrib.file_id = sf.id
            contrib.status = ContributionStatus.PENDIENTE_REVISION.value if sf.status == FileStatus.DISPONIBLE.value else ContributionStatus.BLOQUEADA.value
            db.commit()
        n = db.scalar(select(Contribution).where(Contribution.status == ContributionStatus.BLOQUEADA.value).limit(1))
        if n:
            print("AVISO: hay evidencias bloqueadas (antivirus no disponible). El escenario B no es comparable hasta resolverlo.")
    print(f"Conjunto {a.conjunto} cargado. Participante: evaluador@experimento.test / Experimento-2026")
    if a.solo_cargar:
        return
    import uvicorn

    print(f"Abra http://127.0.0.1:{a.puerto}")
    uvicorn.run("app.main:app", host="127.0.0.1", port=a.puerto, log_level="warning")


if __name__ == "__main__":
    main()
