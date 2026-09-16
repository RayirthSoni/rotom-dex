"""Read only the pinned, hash-verified local PokéAPI cache. Never fetch in queries."""
import csv
import gzip
import hashlib
import io
import json
from pathlib import Path


class PokeAPICache:
    def __init__(self, root: Path):
        self.root = root
        self.manifest = json.loads((root / 'manifest.json').read_text())
        self.sources = {s['id']: s for s in self.manifest['sources']}
        self._raw = {}
        # Verify the entire snapshot before any database writes.
        for name, source in self.sources.items():
            raw = gzip.decompress((root / source['path']).read_bytes())
            if hashlib.sha256(raw).hexdigest() != source['sha256']:
                raise ValueError(f'Source hash mismatch: {name}')
            self._raw[name] = raw

    def rows(self, name: str):
        return csv.DictReader(io.StringIO(self._raw[name].decode('utf-8')))

    def index(self, name: str):
        return {int(r['id']): r for r in self.rows(name)}
