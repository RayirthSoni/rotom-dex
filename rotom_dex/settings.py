"""Runtime settings. The database path comes from ROTOM_DB or the default build location."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path(os.environ.get("ROTOM_DB", ROOT / "data/build/rotom.sqlite3"))
