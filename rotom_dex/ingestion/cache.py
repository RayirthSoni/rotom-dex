"""Read the pinned, hash-verified local PokéAPI CSV cache. Never fetches."""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
from pathlib import Path

ENGLISH = "9"


class PokeAPICache:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.manifest = json.loads((self.root / "manifest.json").read_text())
        self.sources = {s["id"]: s for s in self.manifest["sources"]}
        self._raw: dict[str, bytes] = {}
        self._rows: dict[str, list[dict]] = {}
        # Verify the entire snapshot before any database writes.
        for name, source in self.sources.items():
            raw = gzip.decompress((self.root / source["path"]).read_bytes())
            if hashlib.sha256(raw).hexdigest() != source["sha256"]:
                raise ValueError(f"Source hash mismatch: {name}")
            self._raw[name] = raw

    def manifest_sha256(self) -> str:
        return hashlib.sha256(json.dumps(self.manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def has(self, name: str) -> bool:
        return name in self._raw

    def rows(self, name: str) -> list[dict]:
        if name not in self._rows:
            text = self._raw[name].decode("utf-8")
            self._rows[name] = list(csv.DictReader(io.StringIO(text)))
        return self._rows[name]

    def index(self, name: str, key: str = "id") -> dict[int, dict]:
        return {int(r[key]): r for r in self.rows(name)}

    def english(self, name: str, key: str, field: str = "name") -> dict[int, str]:
        """English text keyed by integer id from a *_names / *_prose style table."""
        out: dict[int, str] = {}
        for r in self.rows(name):
            lang = r.get("local_language_id") or r.get("language_id")
            if lang == ENGLISH:
                out[int(r[key])] = r[field]
        return out
