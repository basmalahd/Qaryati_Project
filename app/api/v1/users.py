from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.auth import RoleUpdate, UserRead
from app.services.auth_service import AuthService

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_me(current: User = Depends(get_current_user)):
    return current


@router.patch("/{user_id}/role", response_model=UserRead)
def update_role(
    user_id: int,
    body: RoleUpdate,
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(Role.ADMIN)),
):
    return AuthService(db).change_role(user_id, body.role)
