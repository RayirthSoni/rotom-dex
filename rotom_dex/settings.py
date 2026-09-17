"""Runtime settings. The database path comes from ROTOM_DB or the default build location."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = Path(os.environ.get("ROTOM_DB", ROOT / "data/build/rotom.sqlite3"))

# Cross-origin access is opt-in. The documented development path is Vite's proxy, which keeps the
# browser on one origin; `rotom serve --cors ORIGIN` is the escape hatch for a split-origin setup.
CORS_ORIGINS = [o.strip() for o in os.environ.get("ROTOM_CORS_ORIGINS", "").split(",") if o.strip()]

# Built single-page application. Mounted only when it exists, so an API-only server still starts.
WEB_DIST = Path(os.environ.get("ROTOM_WEB_DIST", ROOT / "web/dist"))
SERVE_WEB = os.environ.get("ROTOM_SERVE_WEB", "1") != "0"
