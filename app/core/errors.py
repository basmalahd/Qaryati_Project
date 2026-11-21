import logging
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")


class AppError(Exception):
    """Base class for all expected (business) errors."""

    status_code = 500
    code = "INTERNAL_ERROR"

    def __init__(self, message: str, details: list | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or []


class NotFoundError(AppError):
    status_code = 404
    code = "NOT_FOUND"


class ConflictError(AppError):
    status_code = 409
    code = "CONFLICT"


class UnprocessableError(AppError):
    """Request is well-formed but violates a business rule (e.g. unknown reference)."""

    status_code = 422
    code = "UNPROCESSABLE"


class UnauthorizedError(AppError):
    status_code = 401
    code = "UNAUTHORIZED"


class ForbiddenError(AppError):
    status_code = 403
    code = "FORBIDDEN"


def _body(request: Request, status: int, code: str, message: str, details: list | None) -> dict:
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "code": code,
        "message": message,
        "details": details or [],
        "traceId": getattr(request.state, "request_id", uuid.uuid4().hex),
    }


def _response(request, status, code, message, details=None, headers=None) -> JSONResponse:
    return JSONResponse(
        status_code=status, content=_body(request, status, code, message, details), headers=headers
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else None
        return _response(request, exc.status_code, exc.code, exc.message, exc.details, headers)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in e["loc"][1:]), "message": e["msg"]}
            for e in exc.errors()
        ]
        return _response(request, 422, "VALIDATION_ERROR", "Request validation failed", details)

    @app.exception_handler(StarletteHTTPException)
    async def http_handler(request: Request, exc: StarletteHTTPException):
        code = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED"}.get(exc.status_code, "HTTP_ERROR")
        return _response(request, exc.status_code, code, str(exc.detail))

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        # Never leak internals to the client; the traceId lets us find it in the logs.
        trace_id = getattr(request.state, "request_id", "-")
        logger.exception("Unhandled error (traceId=%s)", trace_id)
        return _response(request, 500, "INTERNAL_ERROR", "Unexpected server error")
