from fastapi import FastAPI

from app.api.v1.router import api_router
from app.core.errors import register_exception_handlers
from app.core.middleware import add_request_id_middleware

app = FastAPI(
    title="Qaryati API",
    version="1.0.0",
    description="Palestinian Villages Knowledge Platform",
)

add_request_id_middleware(app)
register_exception_handlers(app)
app.include_router(api_router, prefix="/api/v1")
