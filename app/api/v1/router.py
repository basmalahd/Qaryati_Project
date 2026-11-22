from fastapi import APIRouter

from app.api.v1 import (
    audit, auth, geocoding, governorates, health, nearby, population, sources, stats, users,
    village_content, village_names, villages,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(governorates.router)
api_router.include_router(villages.router)
api_router.include_router(village_names.router)
api_router.include_router(nearby.router)
for content_router in village_content.content_routers:
    api_router.include_router(content_router)
api_router.include_router(population.router)
api_router.include_router(sources.router)
api_router.include_router(geocoding.router)
api_router.include_router(stats.router)
api_router.include_router(audit.router)
