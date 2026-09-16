"""Restore missing source files using the committed manifest; never advance the pin.

Use only after reviewing docs/source-coverage.md. Normal imports are offline.
"""

import gzip
import hashlib
import json
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parents[1] / "data/sources/pokeapi"


def main():
    manifest = json.loads((ROOT / "manifest.json").read_text())
    for source in manifest["sources"]:
        target = ROOT / source["path"]
        if target.exists():
            raw = gzip.decompress(target.read_bytes())
        else:
            with urllib.request.urlopen(source["url"], timeout=60) as response:
                raw = response.read()
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError(f"Hash mismatch for {source['id']}; no file replaced")
        if not target.exists():
            target.write_bytes(gzip.compress(raw, mtime=0))
            print(f"Restored {target.name}")
    print("All cached sources match the pinned manifest.")


if __name__ == "__main__":
    main()
