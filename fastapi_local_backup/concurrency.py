"""Concurrency helpers compatible with FastAPI's public API."""
from __future__ import annotations

from typing import Any, Callable


async def run_in_threadpool(func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Simplified run_in_threadpool that executes the callable immediately."""

    return func(*args, **kwargs)


__all__ = ["run_in_threadpool"]
