from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.village_name import VillageNameCreate, VillageNameItem, VillageNameUpdate
from app.services.village_name_service import VillageNameService

router = APIRouter(prefix="/villages/{village_id}/names", tags=["village names"])


@router.get("", response_model=list[VillageNameItem])
def list_names(
    village_id: int = Path(ge=1), db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    return VillageNameService(db).list(village_id)


@router.post("", response_model=VillageNameItem, status_code=status.HTTP_201_CREATED)
def add_name(
    body: VillageNameCreate,
    village_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.EDITOR, Role.ADMIN)),
):
    return VillageNameService(db).create(village_id, body, actor)


@router.patch("/{name_id}", response_model=VillageNameItem)
def update_name(
    body: VillageNameUpdate,
    village_id: int = Path(ge=1),
    name_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.EDITOR, Role.ADMIN)),
):
    return VillageNameService(db).update(village_id, name_id, body, actor)


@router.delete("/{name_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_name(
    village_id: int = Path(ge=1),
    name_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.ADMIN)),
):
    VillageNameService(db).delete(village_id, name_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
