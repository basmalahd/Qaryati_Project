from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.common import Page
from app.schemas.village import VillageCreate, VillageDetail, VillageSummary, VillageUpdate
from app.services.village_service import VillageService

router = APIRouter(prefix="/villages", tags=["villages"])

SortField = Literal["id", "name_ar", "name_en", "created_at"]
SortOrder = Literal["asc", "desc"]


@router.get("", response_model=Page[VillageSummary])
def list_villages(
    q: str | None = Query(None, max_length=100, description="Search in Arabic/English/alternative names"),
    governorate_id: int | None = Query(None, ge=1),
    sort: SortField = "name_ar",
    order: SortOrder = "asc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return VillageService(db).search(q, governorate_id, sort, order, page, page_size)


@router.get("/{village_id}", response_model=VillageDetail)
def get_village(
    village_id: int, db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    return VillageService(db).get(village_id)


@router.post("", response_model=VillageDetail, status_code=status.HTTP_201_CREATED)
def create_village(
    body: VillageCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.EDITOR, Role.ADMIN)),
):
    return VillageService(db).create(body, actor)


@router.patch("/{village_id}", response_model=VillageDetail)
def update_village(
    village_id: int,
    body: VillageUpdate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.EDITOR, Role.ADMIN)),
):
    return VillageService(db).update(village_id, body, actor)


@router.delete("/{village_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_village(
    village_id: int,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.ADMIN)),
):
    VillageService(db).delete(village_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
