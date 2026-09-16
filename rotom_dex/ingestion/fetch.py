"""Restore or extend the pinned PokéAPI CSV cache. Never advances the revision.

Restore mode re-downloads missing files and verifies them against the manifest.
Add mode fetches additional CSV files at the *same* pinned revision and records
their URL, SHA-256 and retrieval time in the manifest. Adding files changes the
snapshot identity, so existing databases must be rebuilt afterwards.

Normal imports and API requests never call the network.
"""

from __future__ import annotations

import argparse
import datetime as dt
import gzip
import hashlib
import json
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2] / "data/sources/pokeapi"
RAW = "https://raw.githubusercontent.com/PokeAPI/pokeapi/{revision}/data/v2/csv/{name}.csv"


def load_manifest(root: Path = ROOT) -> dict:
    return json.loads((root / "manifest.json").read_text())


def save_manifest(manifest: dict, root: Path = ROOT) -> None:
    (root / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def download(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310
        return response.read()


def restore(root: Path = ROOT) -> list[str]:
    manifest = load_manifest(root)
    restored = []
    for source in manifest["sources"]:
        target = root / source["path"]
        if target.exists():
            raw = gzip.decompress(target.read_bytes())
        else:
            raw = download(source["url"])
        if hashlib.sha256(raw).hexdigest() != source["sha256"]:
            raise ValueError(f"Hash mismatch for {source['id']}; no file replaced")
        if not target.exists():
            target.write_bytes(gzip.compress(raw, mtime=0))
            restored.append(source["id"])
    return restored


def add(names: list[str], root: Path = ROOT, *, ignore_missing: bool = True) -> dict:
    """Fetch new CSV files at the pinned revision and record them in the manifest."""
    manifest = load_manifest(root)
    known = {s["id"] for s in manifest["sources"]}
    added, skipped, missing = [], [], []
    for name in names:
        if name in known:
            skipped.append(name)
            continue
        url = RAW.format(revision=manifest["revision"], name=name)
        try:
            raw = download(url)
        except urllib.error.HTTPError as exc:
            if exc.code == 404 and ignore_missing:
                missing.append(name)
                continue
            raise
        (root / f"{name}.csv.gz").write_bytes(gzip.compress(raw, mtime=0))
        manifest["sources"].append(
            {
                "id": name,
                "url": url,
                "sha256": hashlib.sha256(raw).hexdigest(),
                "retrieved_at": dt.datetime.now(dt.UTC).isoformat(),
                "path": f"{name}.csv.gz",
            }
        )
        known.add(name)
        added.append(name)
    save_manifest(manifest, root)
    return {"added": added, "already_present": skipped, "not_in_upstream": missing}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--add", nargs="*", default=None, metavar="NAME", help="CSV names to add")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    if args.add is not None:
        print(json.dumps(add(args.add, args.root), indent=2))
    else:
        restored = restore(args.root)
        print(json.dumps({"restored": restored, "status": "all cached sources match"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
