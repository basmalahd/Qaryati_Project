from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.cors import configure_cors
from app.core.errors import register_exception_handlers
from app.core.middleware import add_request_id_middleware
from app.core.rate_limit import add_rate_limit_middleware
from app.core.structured_logging import add_access_log_middleware, configure_json_logging

configure_json_logging()

app = FastAPI(
    title="Qaryati API",
    version="1.0.0",
    description="Palestinian Villages Knowledge Platform",
)

# Starlette executes the last added middleware first. Request ID must run
# before logging and rate limiting, including requests rejected with 429.
add_rate_limit_middleware(app)
add_access_log_middleware(app)
add_request_id_middleware(app)
configure_cors(app, settings)
register_exception_handlers(app)
app.include_router(api_router, prefix="/api/v1")
