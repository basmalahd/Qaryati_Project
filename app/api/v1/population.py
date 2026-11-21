from fastapi import APIRouter, Depends, Path, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.population import (
    PopulationCreate, PopulationRead, PopulationStatusUpdate, PopulationUpdate, VerificationStatus,
)
from app.services.population_service import PopulationService

router = APIRouter(prefix="/villages/{village_id}/population", tags=["population"])


@router.get("", response_model=list[PopulationRead])
def population_history(
    village_id: int = Path(ge=1),
    verification_status: VerificationStatus | None = None,
    from_year: int | None = Query(None, ge=1800, le=2100),
    to_year: int | None = Query(None, ge=1800, le=2100),
    db: Session = Depends(get_db),
    _user: User = Depends(get_current_user),
):
    return PopulationService(db).history(village_id, verification_status, from_year, to_year)


@router.post("", response_model=PopulationRead, status_code=status.HTTP_201_CREATED)
def add_population_record(
    body: PopulationCreate,
    village_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.EDITOR, Role.ADMIN)),
):
    return PopulationService(db).create(village_id, body, actor)


@router.patch("/{record_id}", response_model=PopulationRead)
def update_population_record(
    body: PopulationUpdate,
    village_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.EDITOR, Role.ADMIN)),
):
    return PopulationService(db).update(village_id, record_id, body, actor)


@router.patch("/{record_id}/status", response_model=PopulationRead)
def set_population_status(
    body: PopulationStatusUpdate,
    village_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.VERIFIER, Role.ADMIN)),
):
    return PopulationService(db).set_status(village_id, record_id, body.status, actor)


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_population_record(
    village_id: int = Path(ge=1),
    record_id: int = Path(ge=1),
    db: Session = Depends(get_db),
    actor: User = Depends(require_roles(Role.ADMIN)),
):
    PopulationService(db).delete(village_id, record_id, actor)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
