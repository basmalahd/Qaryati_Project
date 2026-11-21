from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog


class AuditRepository:
    def __init__(self, db: Session):
        self.db = db

    def add(self, entry: AuditLog) -> AuditLog:
        self.db.add(entry)
        self.db.flush()
        return entry

    def search(
        self, entity_type: str | None, entity_id: int | None, page: int, page_size: int
    ) -> tuple[list[AuditLog], int]:
        conditions = []
        if entity_type:
            conditions.append(AuditLog.entity_type == entity_type)
        if entity_id is not None:
            conditions.append(AuditLog.entity_id == entity_id)
        total = self.db.scalar(select(func.count(AuditLog.id)).where(*conditions)) or 0
        items = self.db.scalars(
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.id.desc())
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        return list(items), total
