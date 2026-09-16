"""One shared database with a representative game mix, imported once per test session."""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from rotom_dex.db.connection import connect
from rotom_dex.ingestion.pipeline import import_games

GAMES = ["emerald", "ruby", "red", "blue", "platinum", "x", "scarlet"]


@pytest.fixture(scope="session")
def seed_db(tmp_path_factory) -> Path:
    path = tmp_path_factory.mktemp("seed") / "seed.sqlite3"
    summary = import_games(path, GAMES)
    assert summary["games"] == GAMES
    return path


@pytest.fixture(scope="session")
def seed_summary(seed_db):
    return import_games(seed_db, GAMES)  # identical repeat import


@pytest.fixture
def db_path(seed_db, tmp_path) -> Path:
    target = tmp_path / "test.sqlite3"
    shutil.copyfile(seed_db, target)
    return target


@pytest.fixture
def db(db_path):
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture(scope="session")
def client(seed_db):
    os.environ["ROTOM_DB"] = str(seed_db)
    from fastapi.testclient import TestClient

    import rotom_dex.settings as settings

    settings.DEFAULT_DB = seed_db
    import rotom_dex.api.deps as deps

    deps.DEFAULT_DB = seed_db
    import rotom_dex.api.app as app_module

    app_module.DEFAULT_DB = seed_db
    return TestClient(app_module.app)


def dump(conn) -> str:
    return "\n".join(conn.iterdump())


TIMESTAMPED = {"schema_migrations", "snapshots"}  # differ only by creation time between databases


def canonical(conn) -> dict[str, list[tuple]]:
    """Fact-table contents as sorted rows, independent of insertion order and build time."""
    tables = [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
    return {t: sorted(tuple(r) for r in conn.execute(f"SELECT * FROM {t}")) for t in tables if t not in TIMESTAMPED}
