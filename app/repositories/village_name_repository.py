from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.village_name import VillageName


class VillageNameRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_village(self, village_id: int) -> list[VillageName]:
        stmt = (
            select(VillageName)
            .where(VillageName.village_id == village_id)
            .options(joinedload(VillageName.source))
            .order_by(VillageName.id)
        )
        return list(self.db.scalars(stmt).unique())

    def get(self, village_id: int, name_id: int) -> VillageName | None:
        stmt = (
            select(VillageName)
            .where(VillageName.id == name_id, VillageName.village_id == village_id)
            .options(joinedload(VillageName.source))
            .execution_options(populate_existing=True)
        )
        return self.db.scalars(stmt).unique().one_or_none()

    def find_duplicate(
        self, village_id: int, name: str, name_type: str, exclude_id: int | None = None
    ) -> VillageName | None:
        stmt = select(VillageName).where(
            VillageName.village_id == village_id,
            VillageName.name == name,
            VillageName.name_type == name_type,
        )
        if exclude_id is not None:
            stmt = stmt.where(VillageName.id != exclude_id)
        return self.db.scalars(stmt).first()

    def add(self, item: VillageName) -> VillageName:
        self.db.add(item)
        self.db.flush()
        return item

    def delete(self, item: VillageName) -> None:
        self.db.delete(item)
        self.db.flush()
