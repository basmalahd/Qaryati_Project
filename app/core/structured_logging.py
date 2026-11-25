"""JSON request access logging without request/response bodies or credentials."""
import json
import logging
import os
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request

_ACCESS_LOGGER = logging.getLogger("app.access")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key in ("request_id", "method", "path", "status", "duration_ms"):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        if record.exc_info:
            # Avoid logging exception text: upstream libraries may include secrets.
            payload["exception"] = "Unhandled exception"
        return json.dumps(payload, ensure_ascii=False)


def configure_json_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError("LOG_LEVEL must be DEBUG, INFO, WARNING, ERROR or CRITICAL")
    root = logging.getLogger()
    root.setLevel(level)
    # Do not replace other team-owned handlers. Only add one managed JSON handler.
    if not any(getattr(handler, "_qaryati_json", False) for handler in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        handler._qaryati_json = True
        root.addHandler(handler)


def add_access_log_middleware(app: FastAPI) -> None:
    @app.middleware("http")
    async def access_log_middleware(request: Request, call_next):
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            return response
        finally:
            # Do not log query strings, headers, bodies, credentials, or tokens.
            _ACCESS_LOGGER.info(
                "http_request",
                extra={
                    "request_id": getattr(request.state, "request_id", "-"),
                    "method": request.method,
                    "path": request.url.path,
                    "status": status,
                    "duration_ms": round((time.perf_counter() - start) * 1000, 2),
                },
            )
