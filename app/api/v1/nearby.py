from fastapi import APIRouter, Depends, Path, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.nearby import NearbyCreate, NearbyRead
from app.services.nearby_service import NearbyService

router = APIRouter(prefix="/villages/{village_id}/nearby", tags=["nearby places"])


@router.get("", response_model=list[NearbyRead])
def list_nearby(
    village_id: int = Path(ge=1), db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    return NearbyService(db).list(village_id)


@router.post("", response_model=NearbyRead, status_code=status.HTTP_201_CREATED)
def add_nearby(
    body: NearbyCreate,
    village_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.EDITOR, Role.ADMIN)),
):
    return NearbyService(db).create(village_id, body, actor)


@router.delete("/{relation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_nearby(
    village_id: int = Path(ge=1),
    relation_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.ADMIN)),
):
    NearbyService(db).delete(village_id, relation_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
