from fastapi import APIRouter

from app.api.v1 import audit, auth, governorates, health, stats, users, villages

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(governorates.router)
api_router.include_router(villages.router)
api_router.include_router(stats.router)
api_router.include_router(audit.router)
