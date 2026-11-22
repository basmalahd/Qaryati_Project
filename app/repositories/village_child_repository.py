from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload


class VillageChildRepository:
    """Data access shared by every table that belongs to one village (events, landmarks, ...)."""

    def __init__(self, db: Session, model: type):
        self.db = db
        self.model = model

    def list_for_village(
        self,
        village_id: int,
        filters: dict[str, Any] | None = None,
        extra: list | None = None,
        order_by: list | None = None,
    ) -> list:
        m = self.model
        conditions = [m.village_id == village_id]
        conditions += [getattr(m, k) == v for k, v in (filters or {}).items() if v is not None]
        conditions += extra or []
        stmt = (
            select(m)
            .where(*conditions)
            .options(joinedload(m.source))
            .order_by(*(order_by or [m.id]))
        )
        return list(self.db.scalars(stmt).unique())

    def get(self, village_id: int, item_id: int):
        m = self.model
        stmt = (
            select(m)
            .where(m.id == item_id, m.village_id == village_id)
            .options(joinedload(m.source))
            .execution_options(populate_existing=True)
        )
        return self.db.scalars(stmt).unique().one_or_none()

    def find_duplicate(self, village_id: int, keys: dict[str, Any], exclude_id: int | None = None):
        m = self.model
        stmt = select(m).where(m.village_id == village_id, *[getattr(m, k) == v for k, v in keys.items()])
        if exclude_id is not None:
            stmt = stmt.where(m.id != exclude_id)
        return self.db.scalars(stmt).first()

    def add(self, item):
        self.db.add(item)
        self.db.flush()
        return item

    def delete(self, item) -> None:
        self.db.delete(item)
        self.db.flush()
