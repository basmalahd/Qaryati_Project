"""Per-process, per-IP sliding-window rate limiting.

For multiple workers or replicas, use a shared backend (for example Redis).
Do not trust client-supplied forwarding headers for IP identification.
"""

import os
import threading
import time
from collections import defaultdict, deque
from math import ceil

from fastapi import FastAPI, Request
from starlette.responses import Response

from app.core.errors import _response

_WINDOW_SECONDS = 60
_lock = threading.Lock()
_hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)


def _enabled() -> bool:
    return os.getenv("RATE_LIMIT_ENABLED", "true").strip().lower() not in {
        "0", "false", "no", "off"
    }


def _positive_int(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
        if value < 1:
            raise ValueError
        return value
    except ValueError as exc:
        raise ValueError(f"{name} must be a positive integer") from exc


def _rule(path: str) -> tuple[str, int]:
    normalized = path.rstrip("/") or "/"
    if normalized == "/api/v1/auth/login":
        return "login", _positive_int("RATE_LIMIT_LOGIN_PER_MINUTE", 5)
    if normalized == "/api/v1/auth/register":
        return "register", _positive_int("RATE_LIMIT_REGISTER_PER_MINUTE", 3)
    return "general", _positive_int("RATE_LIMIT_GENERAL_PER_MINUTE", 120)


def _client_ip(request: Request) -> str:
    # The ASGI server / trusted ingress should resolve proxy addresses.
    return request.client.host if request.client else "unknown"


def _allow(ip: str, bucket: str, limit: int, now: float) -> int:
    """Return seconds until retry (zero means the request is allowed)."""
    with _lock:
        queue = _hits[(ip, bucket)]
        while queue and queue[0] <= now - _WINDOW_SECONDS:
            queue.popleft()
        if len(queue) >= limit:
            return max(1, ceil(_WINDOW_SECONDS - (now - queue[0])))
        queue.append(now)
        return 0


def add_rate_limit_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def rate_limit_middleware(request: Request, call_next) -> Response:
        if not _enabled() or request.method == "OPTIONS":
            return await call_next(request)

        bucket, limit = _rule(request.url.path)
        retry_after = _allow(_client_ip(request), bucket, limit, time.monotonic())
        if retry_after:
            response = _response(
                request,
                429,
                "RATE_LIMITED",
                "Too many requests. Try again later.",
                headers={"Retry-After": str(retry_after)},
            )
            # Ensure this header exists even when request-id middleware is inner.
            request_id = getattr(request.state, "request_id", None)
            if request_id:
                response.headers["X-Request-ID"] = request_id
            return response
        return await call_next(request)


def clear_rate_limits() -> None:
    """Reset in-memory counters for deterministic tests."""
    with _lock:
        _hits.clear()
