from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.content import (
    EconomicCategory, EconomicCreate, EconomicRead, EconomicUpdate, EventCreate, EventRead,
    EventUpdate, FacilityCreate, FacilityRead, FacilityType, FacilityUpdate, HeritageCategory,
    HeritageCreate, HeritageRead, HeritageUpdate, LandmarkCategory, LandmarkCreate, LandmarkRead,
    LandmarkUpdate,
)
from app.services.village_content_service import (
    EconomyService, EventService, FacilityService, HeritageService, LandmarkService,
)

WRITERS = (Role.EDITOR, Role.ADMIN)


def _mount_write_routes(router: APIRouter, service_cls, create_schema, update_schema, read_schema):
    """POST / PATCH / DELETE are identical for every village-content resource."""

    @router.post("", response_model=read_schema, status_code=status.HTTP_201_CREATED)
    def create(
        body: create_schema,
        village_id: int = Path(ge=1),
        db: Session = Depends(get_db),
        actor: User = Depends(require_roles(*WRITERS)),
    ):
        return service_cls(db).create(village_id, body, actor)

    @router.patch("/{item_id}", response_model=read_schema)
    def update(
        body: update_schema,
        village_id: int = Path(ge=1),
        item_id: int = Path(ge=1),
        db: Session = Depends(get_db),
        actor: User = Depends(require_roles(*WRITERS)),
    ):
        return service_cls(db).update(village_id, item_id, body, actor)

    @router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete(
        village_id: int = Path(ge=1),
        item_id: int = Path(ge=1),
        db: Session = Depends(get_db),
        actor: User = Depends(require_roles(Role.ADMIN)),
    ):
        service_cls(db).delete(village_id, item_id, actor)
        return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- history / timeline ------------------------------------------------
events_router = APIRouter(prefix="/villages/{village_id}/events", tags=["history"])


@events_router.get("", response_model=list[EventRead])
def list_events(
    village_id: int = Path(ge=1),
    from_year: int | None = Query(None, ge=-3000, le=2100),
    to_year: int | None = Query(None, ge=-3000, le=2100),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return EventService(db).list(village_id, from_year, to_year)


_mount_write_routes(events_router, EventService, EventCreate, EventUpdate, EventRead)

# ---- landmarks ---------------------------------------------------------
landmarks_router = APIRouter(prefix="/villages/{village_id}/landmarks", tags=["landmarks"])


@landmarks_router.get("", response_model=list[LandmarkRead])
def list_landmarks(
    village_id: int = Path(ge=1),
    category: LandmarkCategory | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return LandmarkService(db).list(village_id, category)


_mount_write_routes(landmarks_router, LandmarkService, LandmarkCreate, LandmarkUpdate, LandmarkRead)

# ---- heritage ----------------------------------------------------------
heritage_router = APIRouter(prefix="/villages/{village_id}/heritage", tags=["heritage"])


@heritage_router.get("", response_model=list[HeritageRead])
def list_heritage(
    village_id: int = Path(ge=1),
    category: HeritageCategory | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return HeritageService(db).list(village_id, category)


_mount_write_routes(heritage_router, HeritageService, HeritageCreate, HeritageUpdate, HeritageRead)

# ---- economy -----------------------------------------------------------
economy_router = APIRouter(prefix="/villages/{village_id}/economy", tags=["economy"])


@economy_router.get("", response_model=list[EconomicRead])
def list_economy(
    village_id: int = Path(ge=1),
    category: EconomicCategory | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return EconomyService(db).list(village_id, category)


_mount_write_routes(economy_router, EconomyService, EconomicCreate, EconomicUpdate, EconomicRead)

# ---- facilities --------------------------------------------------------
facilities_router = APIRouter(prefix="/villages/{village_id}/facilities", tags=["facilities"])


@facilities_router.get("", response_model=list[FacilityRead])
def list_facilities(
    village_id: int = Path(ge=1),
    facility_type: FacilityType | None = None,
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return FacilityService(db).list(village_id, facility_type)


_mount_write_routes(facilities_router, FacilityService, FacilityCreate, FacilityUpdate, FacilityRead)

content_routers = [
    events_router, landmarks_router, heritage_router, economy_router, facilities_router,
]
