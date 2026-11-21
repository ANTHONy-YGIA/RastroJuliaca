"""Aplicación FastAPI de RastroJuliaca."""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config import get_settings
from .routers import account, admin, auth, cases, contributions, files, public, reports, review
from .services import storage

settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    storage.dirs()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="RastroJuliaca API",
    version="0.1.0",
    description="Gestión y revisión colaborativa de evidencias digitales (MVP de demostración).",
    docs_url="/api/docs" if settings.env != "production" else None,
    redoc_url=None,
    openapi_url="/api/openapi.json" if settings.env != "production" else None,
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

CSP = (
    "default-src 'self'; img-src 'self' blob: data:; media-src 'self' blob:; "
    "style-src 'self' 'unsafe-inline'; script-src 'self'; font-src 'self' data:; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


MAX_BODY_BYTES = (max(settings.max_video_mb, settings.max_image_mb, settings.max_document_mb) + 1) * 1024 * 1024


@app.middleware("http")
async def body_size_limit(request: Request, call_next):
    """Rechaza cuerpos excesivos ANTES de que el servidor los escriba en disco temporal."""
    if request.method in ("POST", "PUT", "PATCH"):
        length = request.headers.get("content-length")
        if length is None and "chunked" in request.headers.get("transfer-encoding", "").lower():
            return JSONResponse(status_code=411, content={"detail": "Se requiere Content-Length"})
        if length is not None:
            try:
                too_big = int(length) > MAX_BODY_BYTES
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Content-Length inválido"})
            if too_big:
                return JSONResponse(status_code=413, content={"detail": "La solicitud supera el tamaño máximo permitido"})
    return await call_next(request)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=(self)")
    if not request.url.path.startswith("/api/docs"):
        response.headers.setdefault("Content-Security-Policy", CSP)
    if request.url.path.startswith("/api/"):
        response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    fields = {}
    for err in exc.errors():
        loc = [str(p) for p in err.get("loc", []) if p not in ("body", "query", "path")]
        fields[".".join(loc) or "general"] = err.get("msg", "Valor inválido")
    return JSONResponse(status_code=422, content={"detail": {"message": "Datos inválidos", "fields": fields}})


for r in (auth, public, cases, contributions, review, reports, files, account, admin):
    app.include_router(r.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "demo_mode": settings.demo_mode}



# ---------------------------------------------------------------- frontend compilado (SPA)
dist = Path(settings.frontend_dist)
if (dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
def spa(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404, "Ruta no encontrada")
    index = dist / "index.html"
    candidate = (dist / full_path).resolve()
    if full_path and candidate.is_file() and dist.resolve() in candidate.parents:
        return FileResponse(candidate)
    if index.exists():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return JSONResponse({"message": "Frontend no compilado. Ejecute scripts/setup.ps1"}, status_code=503)
