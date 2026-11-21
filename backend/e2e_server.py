"""Servidor aislado para pruebas E2E (Playwright): BD y almacenamiento propios, datos ficticios recreados."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("RJ_DATABASE_URL", f"sqlite:///{(ROOT / 'data' / 'e2e.db').as_posix()}")
os.environ.setdefault("RJ_STORAGE_DIR", str(ROOT / "data" / "e2e-storage"))
os.environ.setdefault("RJ_DEMO_MODE", "true")
os.environ.setdefault("RJ_RATE_LOGIN", "500")
os.environ.setdefault("RJ_RATE_REGISTER", "500")
sys.path.insert(0, str(Path(__file__).resolve().parent))

if __name__ == "__main__":
    from app.seed import main as seed_main

    seed_main(["--reset"])
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ.get("RJ_E2E_PORT", "8001")), log_level="warning")
