from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.nearby_place import NearbyPlace


class NearbyRepository:
    def __init__(self, db: Session):
        self.db = db

    def _with_relations(self, stmt):
        return stmt.options(joinedload(NearbyPlace.related_village), joinedload(NearbyPlace.source))

    def list_for_village(self, village_id: int) -> list[NearbyPlace]:
        stmt = self._with_relations(
            select(NearbyPlace)
            .where(NearbyPlace.village_id == village_id)
            .order_by(NearbyPlace.relation_type, NearbyPlace.id)
        )
        return list(self.db.scalars(stmt).unique())

    def get(self, village_id: int, relation_id: int) -> NearbyPlace | None:
        stmt = self._with_relations(
            select(NearbyPlace)
            .where(NearbyPlace.id == relation_id, NearbyPlace.village_id == village_id)
            .execution_options(populate_existing=True)
        )
        return self.db.scalars(stmt).unique().one_or_none()

    def find_duplicate(
        self, village_id: int, related_village_id: int | None, place_name: str | None, relation_type: str
    ) -> NearbyPlace | None:
        stmt = select(NearbyPlace).where(
            NearbyPlace.village_id == village_id, NearbyPlace.relation_type == relation_type
        )
        if related_village_id is not None:
            stmt = stmt.where(NearbyPlace.related_village_id == related_village_id)
        else:
            stmt = stmt.where(NearbyPlace.place_name == place_name)
        return self.db.scalars(stmt).first()

    def add(self, item: NearbyPlace) -> NearbyPlace:
        self.db.add(item)
        self.db.flush()
        return item

    def delete(self, item: NearbyPlace) -> None:
        self.db.delete(item)
        self.db.flush()
