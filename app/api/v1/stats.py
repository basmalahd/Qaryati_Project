from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.governorate import GovernorateVillageCount
from app.services.village_service import VillageService

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/villages-by-governorate", response_model=list[GovernorateVillageCount])
def villages_by_governorate(
    db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    return VillageService(db).stats_by_governorate()
