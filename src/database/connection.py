"""Schema v1 is created only on an empty database; future changes need migrations."""
import sqlite3
from pathlib import Path


def connect(path: str | Path, *, readonly: bool = False) -> sqlite3.Connection:
    target = Path(path).resolve().as_uri() + '?mode=ro' if readonly else str(path)
    db = sqlite3.connect(target, uri=readonly)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA foreign_keys = ON')
    return db


def initialize(db: sqlite3.Connection) -> None:
    tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not tables:
        db.executescript(Path(__file__).with_name('schema.sql').read_text())
    elif 'schema_version' not in tables or [r[0] for r in db.execute('SELECT version FROM schema_version')] != [1]:
        raise ValueError('Unsupported database schema; create a fresh snapshot database')
