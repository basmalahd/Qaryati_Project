from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.models.nearby_place import NearbyPlace
from app.models.user import User
from app.repositories.nearby_repository import NearbyRepository
from app.repositories.source_repository import SourceRepository
from app.repositories.village_repository import VillageRepository
from app.schemas.nearby import NearbyCreate
from app.services.audit_service import AuditService

_FIELDS = (
    "village_id", "related_village_id", "place_name", "relation_type",
    "distance_km", "direction", "source_id",
)


def _snapshot(n: NearbyPlace) -> dict:
    return {"id": n.id, **{f: getattr(n, f) for f in _FIELDS}}


class NearbyService:
    """Geographic relations of a village (neighbouring villages or nearby cities).

    Relations are directional and are not mirrored automatically: no hidden writes.
    """

    def __init__(self, db: Session):
        self.db = db
        self.nearby = NearbyRepository(db)
        self.villages = VillageRepository(db)
        self.sources = SourceRepository(db)
        self.audit = AuditService(db)

    def list(self, village_id: int) -> list[NearbyPlace]:
        self._require_village(village_id)
        return self.nearby.list_for_village(village_id)

    def create(self, village_id: int, data: NearbyCreate, actor: User) -> NearbyPlace:
        self._require_village(village_id)
        if data.related_village_id is not None:
            if data.related_village_id == village_id:
                raise UnprocessableError(
                    "A village cannot be related to itself",
                    [{"field": "related_village_id", "message": "must differ from the village"}],
                )
            if not self.villages.get(data.related_village_id):
                raise UnprocessableError(
                    "Related village does not exist",
                    [{"field": "related_village_id", "message": "unknown village"}],
                )
        if data.source_id is not None and not self.sources.get(data.source_id):
            raise UnprocessableError(
                "Source does not exist", [{"field": "source_id", "message": "unknown source"}]
            )
        if self.nearby.find_duplicate(
            village_id, data.related_village_id, data.place_name, data.relation_type
        ):
            raise ConflictError(
                "This relation already exists", [{"field": "relation_type", "message": "duplicate"}]
            )

        item = self.nearby.add(NearbyPlace(village_id=village_id, **data.model_dump()))
        self.audit.record(actor, "create", "nearby_place", item.id, {"after": _snapshot(item)})
        self.db.commit()
        return self.nearby.get(village_id, item.id)

    def delete(self, village_id: int, relation_id: int, actor: User) -> None:
        self._require_village(village_id)
        item = self.nearby.get(village_id, relation_id)
        if not item:
            raise NotFoundError("Relation not found")
        snapshot = _snapshot(item)
        self.nearby.delete(item)
        self.audit.record(actor, "delete", "nearby_place", relation_id, {"before": snapshot})
        self.db.commit()

    def _require_village(self, village_id: int) -> None:
        if not self.villages.get(village_id):
            raise NotFoundError("Village not found")
