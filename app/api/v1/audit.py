from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.user import Role, User
from app.schemas.audit import AuditLogRead
from app.schemas.common import Page, build_page
from app.services.audit_service import AuditService

router = APIRouter(prefix="/audit-logs", tags=["audit"])


@router.get("", response_model=Page[AuditLogRead])
def list_audit_logs(
    entity_type: str | None = Query(None, max_length=50),
    entity_id: int | None = Query(None, ge=1),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _admin: User = Depends(require_roles(Role.ADMIN)),
):
    items, total = AuditService(db).search(entity_type, entity_id, page, page_size)
    return build_page(items, total, page, page_size)
