from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.governorate import GovernorateVillageCount
from app.schemas.population import LatestVillagePopulation
from app.services.population_service import PopulationService
from app.services.village_service import VillageService

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/villages-by-governorate", response_model=list[GovernorateVillageCount])
def villages_by_governorate(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    return VillageService(db).stats_by_governorate()


@router.get("/latest-population", response_model=list[LatestVillagePopulation])
def latest_population(
    governorate_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    """Latest non-disputed population record per village, largest villages first."""
    return PopulationService(db).latest_per_village(governorate_id, limit)
