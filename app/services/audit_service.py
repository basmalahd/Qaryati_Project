from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.user import User
from app.repositories.audit_repository import AuditRepository


class AuditService:
    def __init__(self, db: Session):
        self.repo = AuditRepository(db)

    def record(self, actor: User, action: str, entity_type: str, entity_id: int, changes: dict):
        """Adds the entry to the *current* transaction; the caller commits."""
        self.repo.add(
            AuditLog(
                user_id=actor.id,
                action=action,
                entity_type=entity_type,
                entity_id=entity_id,
                changes=changes,
            )
        )

    def search(self, entity_type, entity_id, page, page_size):
        return self.repo.search(entity_type, entity_id, page, page_size)
