from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.api.deps import get_geocoder, require_roles
from app.db.session import get_db
from app.integrations.geocoding import GeocodingProvider
from app.models.user import Role, User
from app.schemas.geocoding import GeoCandidate, LocationSuggestions
from app.services.location_service import LocationService

router = APIRouter(tags=["geocoding"])


@router.get("/geocoding/search", response_model=list[GeoCandidate])
def search_places(
    q: str = Query(..., min_length=2, max_length=100),
    limit: int = Query(5, ge=1, le=10),
    db: Session = Depends(get_db),
    geocoder: GeocodingProvider = Depends(get_geocoder),
    _actor: User = Depends(require_roles(Role.EDITOR, Role.ADMIN)),
):
    return LocationService(db, geocoder).search(q, limit)


@router.get("/villages/{village_id}/location-suggestions", response_model=LocationSuggestions)
def location_suggestions(
    village_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    geocoder: GeocodingProvider = Depends(get_geocoder),
    _actor: User = Depends(require_roles(Role.EDITOR, Role.ADMIN)),
):
    return LocationService(db, geocoder).suggest_for_village(village_id)
