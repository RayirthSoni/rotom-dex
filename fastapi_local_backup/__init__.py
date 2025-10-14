"""Lightweight FastAPI-compatible shims for local testing."""
from __future__ import annotations

import asyncio
import inspect
from types import SimpleNamespace
from typing import Any, Awaitable, Callable, Dict, Optional, Tuple


class HTTPException(Exception):
    """Simple HTTP exception carrying status code and detail."""

    def __init__(self, status_code: int, detail: Any) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


RouteKey = Tuple[str, str]


class FastAPI:
    """Minimal subset of FastAPI used for unit testing the service module."""

    def __init__(self, *, title: Optional[str] = None) -> None:
        self.title = title or "FastAPI"
        self.state = SimpleNamespace()
        self._routes: Dict[RouteKey, Callable[..., Any]] = {}

    def post(self, path: str, response_model: Any | None = None) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            self._routes[("POST", path)] = func
            return func

        return decorator

    def _lookup(self, method: str, path: str) -> Callable[..., Any]:
        try:
            return self._routes[(method.upper(), path)]
        except KeyError as exc:
            raise RuntimeError(f"No route registered for {method} {path}") from exc


def _serialize_response(result: Any) -> Any:
    if result is None:
        return None
    if hasattr(result, "model_dump"):
        return result.model_dump()
    if hasattr(result, "dict"):
        return result.dict()
    return result


def _parse_arguments(func: Callable[..., Any], json_payload: Dict[str, Any]) -> Tuple[Any, ...]:
    signature = inspect.signature(func)
    if not signature.parameters:
        return tuple()
    param = next(iter(signature.parameters.values()))
    annotation = param.annotation
    if isinstance(annotation, str):
        annotation = func.__globals__.get(annotation, annotation)
    if annotation is inspect._empty:  # type: ignore[attr-defined]
        return (json_payload,)
    parser = getattr(annotation, "parse_obj", None) or getattr(annotation, "model_validate", None)
    if parser is not None:
        return (parser(json_payload),)
    return (annotation(**json_payload) if callable(annotation) else json_payload,)


def _ensure_awaitable(value: Any) -> Awaitable[Any]:
    if inspect.isawaitable(value):
        return value  # type: ignore[return-value]

    async def _wrapper() -> Any:
        return value

    return _wrapper()


class _Response:
    def __init__(self, status_code: int, payload: Any) -> None:
        self.status_code = status_code
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class TestClient:
    """Synchronous test client similar to fastapi.testclient.TestClient."""

    def __init__(self, app: FastAPI) -> None:
        self.app = app

    def post(self, path: str, json: Optional[Dict[str, Any]] = None) -> _Response:
        handler = self.app._lookup("POST", path)
        json_payload = json or {}
        args = _parse_arguments(handler, json_payload)
        try:
            result = asyncio.run(_ensure_awaitable(handler(*args)))
        except HTTPException as exc:
            return _Response(exc.status_code, {"detail": exc.detail})
        return _Response(200, _serialize_response(result))


__all__ = ["FastAPI", "HTTPException", "TestClient"]

# Avoid pytest mistaking TestClient for a test class
TestClient.__test__ = False  # type: ignore[attr-defined]
