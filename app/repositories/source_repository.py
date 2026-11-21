from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.source import Source
from app.repositories.utils import escape_like


class SourceRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, source_id: int) -> Source | None:
        return self.db.get(Source, source_id)

    def search(
        self, q: str | None, source_type: str | None, page: int, page_size: int
    ) -> tuple[list[Source], int]:
        conditions = []
        if q:
            pattern = f"%{escape_like(q.strip())}%"
            conditions.append(
                or_(Source.title.ilike(pattern, escape="\\"), Source.author.ilike(pattern, escape="\\"))
            )
        if source_type:
            conditions.append(Source.source_type == source_type)

        total = self.db.scalar(select(func.count(Source.id)).where(*conditions)) or 0
        items = self.db.scalars(
            select(Source)
            .where(*conditions)
            .order_by(Source.title, Source.id)
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        return list(items), total

    def add(self, source: Source) -> Source:
        self.db.add(source)
        self.db.flush()
        return source
