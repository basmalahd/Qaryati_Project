from sqlalchemy.orm import Session

from app.core.errors import NotFoundError
from app.models.source import Source
from app.models.user import User
from app.repositories.source_repository import SourceRepository
from app.schemas.common import build_page
from app.schemas.source import SourceCreate, SourceUpdate
from app.services.audit_service import AuditService

_FIELDS = ("title", "source_type", "author", "url", "publication_year", "notes")


def _snapshot(s: Source) -> dict:
    return {"id": s.id, **{f: getattr(s, f) for f in _FIELDS}}


class SourceService:
    def __init__(self, db: Session):
        self.db = db
        self.sources = SourceRepository(db)
        self.audit = AuditService(db)

    def search(self, q, source_type, page, page_size) -> dict:
        items, total = self.sources.search(q, source_type, page, page_size)
        return build_page(items, total, page, page_size)

    def get(self, source_id: int) -> Source:
        source = self.sources.get(source_id)
        if not source:
            raise NotFoundError("Source not found")
        return source

    def create(self, data: SourceCreate, actor: User) -> Source:
        source = self.sources.add(Source(**data.model_dump()))
        self.audit.record(actor, "create", "source", source.id, {"after": _snapshot(source)})
        self.db.commit()
        self.db.refresh(source)
        return source

    def update(self, source_id: int, data: SourceUpdate, actor: User) -> Source:
        source = self.get(source_id)
        before, after = {}, {}
        for field, new_value in data.model_dump(exclude_unset=True).items():
            old_value = getattr(source, field)
            if old_value != new_value:
                before[field], after[field] = old_value, new_value
                setattr(source, field, new_value)
        if not after:
            return source
        self.audit.record(actor, "update", "source", source.id, {"before": before, "after": after})
        self.db.commit()
        self.db.refresh(source)
        return source
