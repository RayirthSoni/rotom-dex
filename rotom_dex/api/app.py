"""FastAPI application. Every request reads the local snapshot database; nothing calls the network."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from rotom_dex.api.routers import analysis, catalog, chat, pokemon, resources
from rotom_dex.api.schemas import Problem, ValidationProblem
from rotom_dex.chat.errors import ProviderTimeout, ProviderUnavailable
from rotom_dex.db.connection import connect
from rotom_dex.errors import NotFound, SemanticError, StaleDatabase
from rotom_dex.repositories.common import snapshot_id
from rotom_dex.settings import CORS_ORIGINS, DEFAULT_DB, SERVE_WEB, WEB_DIST

ERROR_RESPONSES = {
    400: {"model": Problem, "description": "Meaningless inside the requested game"},
    404: {"model": Problem, "description": "Unknown game or identifier"},
    422: {"model": ValidationProblem, "description": "Parameter or body validation failed"},
    429: {"model": Problem, "description": "Too many chat requests from this client"},
    503: {"model": Problem, "description": "The snapshot database is missing, or the chat provider is unavailable"},
    504: {"model": Problem, "description": "The chat provider did not answer in time"},
}

app = FastAPI(
    title="Rotom Dex API",
    version="0.4.0",
    description="Evidence-backed, game-scoped Pokémon data. Pass `game` (exact version slug) to every game-scoped endpoint; responses carry coverage, assumptions and evidence.",
)

if CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=CORS_ORIGINS,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

for router in (catalog.router, pokemon.router, resources.router, analysis.router, chat.router):
    app.include_router(router, prefix="/api", responses=ERROR_RESPONSES)


@app.exception_handler(NotFound)
def not_found(_: Request, exc: NotFound):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(SemanticError)
def bad_request(_: Request, exc: SemanticError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(StaleDatabase)
def stale_database(_: Request, exc: StaleDatabase):
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(ProviderUnavailable)
def provider_unavailable(_: Request, exc: ProviderUnavailable):
    # 503, the same shape a missing database gets: the model is an optional component, and every
    # other endpoint keeps working while it is down.
    return JSONResponse(status_code=503, content={"detail": str(exc)})


@app.exception_handler(ProviderTimeout)
def provider_timeout(_: Request, exc: ProviderTimeout):
    return JSONResponse(status_code=504, content={"detail": str(exc)})


@app.exception_handler(FileNotFoundError)
def no_database(_: Request, exc: FileNotFoundError):
    return JSONResponse(status_code=503, content={"detail": f"{exc}; run `rotom import` first"})


@app.get("/health")
def health():
    db = connect(DEFAULT_DB, readonly=True, same_thread=False)
    try:
        return {"status": "ok", "snapshot_id": snapshot_id(db), "database": str(DEFAULT_DB)}
    finally:
        db.close()


# The built single-page application, when one exists. Registered last so it can never shadow /api,
# and with an explicit fallback because StaticFiles alone returns 404 for client-side routes.
_index = WEB_DIST / "index.html"
if SERVE_WEB and _index.is_file():
    _assets = WEB_DIST / "assets"
    if _assets.is_dir():
        app.mount("/assets", StaticFiles(directory=_assets), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith(("api/", "health", "docs", "redoc", "openapi.json")):
            return JSONResponse(status_code=404, content={"detail": f"No such endpoint: /{path}"})
        candidate = (WEB_DIST / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(WEB_DIST.resolve()):
            return FileResponse(candidate)
        return FileResponse(_index)
