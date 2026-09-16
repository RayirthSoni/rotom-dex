"""FastAPI application. Every request reads the local snapshot database; nothing calls the network."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from rotom_dex.api.routers import catalog, pokemon, resources
from rotom_dex.db.connection import connect
from rotom_dex.repositories.common import NotFound, snapshot_id
from rotom_dex.settings import DEFAULT_DB

app = FastAPI(
    title="Rotom Dex API",
    version="0.2.0",
    description="Evidence-backed, game-scoped Pokémon data. Pass `game` (exact version slug) to every game-scoped endpoint; responses carry coverage, assumptions and evidence.",
)
app.include_router(catalog.router, prefix="/api")
app.include_router(pokemon.router, prefix="/api")
app.include_router(resources.router, prefix="/api")


@app.exception_handler(NotFound)
def not_found(_: Request, exc: NotFound):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(ValueError)
def bad_request(_: Request, exc: ValueError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(FileNotFoundError)
def no_database(_: Request, exc: FileNotFoundError):
    return JSONResponse(status_code=503, content={"detail": f"{exc}; run `rotom import` first"})


@app.get("/health")
def health():
    db = connect(DEFAULT_DB, readonly=True)
    try:
        return {"status": "ok", "snapshot_id": snapshot_id(db), "database": str(DEFAULT_DB)}
    finally:
        db.close()
