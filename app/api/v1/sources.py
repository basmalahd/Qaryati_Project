from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.common import Page
from app.schemas.source import SourceCreate, SourceRead, SourceType, SourceUpdate
from app.services.source_service import SourceService

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=Page[SourceRead])
def list_sources(
    q: str | None = Query(None, max_length=100, description="Search in title/author"),
    source_type: SourceType | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return SourceService(db).search(q, source_type, page, page_size)


@router.get("/{source_id}", response_model=SourceRead)
def get_source(
    source_id: int = Path(ge=1), db: Session = Depends(get_db), _user: User = Depends(get_current_user)
):
    return SourceService(db).get(source_id)


@router.post("", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(
    body: SourceCreate,
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.EDITOR, Role.ADMIN)),
):
    return SourceService(db).create(body, actor)


@router.patch("/{source_id}", response_model=SourceRead)
def update_source(
    body: SourceUpdate,
    source_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.EDITOR, Role.ADMIN)),
):
    return SourceService(db).update(source_id, body, actor)
