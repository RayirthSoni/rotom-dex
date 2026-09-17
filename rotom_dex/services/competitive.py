"""Pinned, local Node calculators. No model or network is involved."""

from __future__ import annotations

import json
import shutil
import subprocess
import threading
from functools import lru_cache
from pathlib import Path

from rotom_dex.errors import SemanticError

BRIDGE = Path(__file__).resolve().parents[2] / "battle" / "bridge.cjs"


_SLOTS = threading.BoundedSemaphore(4)


def run(operation: str, **payload):
    node = shutil.which("node")
    if not node or not (BRIDGE.parent / "node_modules").exists():
        raise SemanticError("Competitive tools need Node and the battle dependencies. Run npm ci --prefix battle.")
    encoded = json.dumps({"operation": operation, **payload})
    if len(encoded) > 50_000:
        raise SemanticError("The team or calculation is too large.")
    if not _SLOTS.acquire(blocking=False):
        raise SemanticError("Battle tools are busy. Try again shortly.")
    try:
        result = subprocess.run([node, str(BRIDGE)], input=encoded + "\n", text=True, capture_output=True, timeout=12, check=True)
        reply = json.loads(result.stdout.strip())
    except (subprocess.SubprocessError, ValueError):
        raise SemanticError("The battle calculator could not finish this request. Check the set and format.") from None
    finally:
        _SLOTS.release()
    if not reply["ok"]:
        raise SemanticError(reply["error"])
    return reply["data"]


@lru_cache(maxsize=1)
def formats():
    return run("formats")
