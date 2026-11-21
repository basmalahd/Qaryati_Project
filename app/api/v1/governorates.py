from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.governorate import GovernorateCreate, GovernorateRead
from app.services.governorate_service import GovernorateService

router = APIRouter(prefix="/governorates", tags=["governorates"])


@router.get("", response_model=list[GovernorateRead])
def list_governorates(db: Session = Depends(get_db), _user: User = Depends(get_current_user)):
    return GovernorateService(db).list_all()


@router.post("", response_model=GovernorateRead, status_code=status.HTTP_201_CREATED)
def create_governorate(
    body: GovernorateCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_roles(Role.ADMIN)),
):
    return GovernorateService(db).create(body, admin)
