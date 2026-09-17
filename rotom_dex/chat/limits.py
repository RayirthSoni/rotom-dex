"""Per-process limits. A key digest is held only while its requests are active."""

import hashlib
import threading

from fastapi import HTTPException

_lock = threading.Lock()
_active: dict[str, int] = {}


def acquire(key: str | None) -> str:
    identity = hashlib.sha256((key or "anonymous").encode()).hexdigest()
    with _lock:
        if sum(_active.values()) >= 12 or _active.get(identity, 0) >= 2:
            raise HTTPException(429, "Too many simultaneous requests. Wait for an answer or cancel it first.")
        _active[identity] = _active.get(identity, 0) + 1
    return identity


def release(identity: str):
    with _lock:
        remaining = _active.get(identity, 1) - 1
        if remaining:
            _active[identity] = remaining
        else:
            _active.pop(identity, None)
