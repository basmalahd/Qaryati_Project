from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.models.user import User
from app.models.village import Village
from app.models.village_name import VillageName
from app.repositories.source_repository import SourceRepository
from app.repositories.village_name_repository import VillageNameRepository
from app.repositories.village_repository import VillageRepository
from app.schemas.village_name import VillageNameCreate, VillageNameUpdate
from app.services.audit_service import AuditService

_FIELDS = ("village_id", "name", "language", "name_type", "period_note", "source_id")


def _snapshot(n: VillageName) -> dict:
    return {"id": n.id, **{f: getattr(n, f) for f in _FIELDS}}


class VillageNameService:
    """Alternative spellings, transliterations, former and historical names.

    Rules: the name must differ from the village's current name; one entry per
    (village, name, type); a cited source must exist.
    """

    def __init__(self, db: Session):
        self.db = db
        self.names = VillageNameRepository(db)
        self.villages = VillageRepository(db)
        self.sources = SourceRepository(db)
        self.audit = AuditService(db)

    def list(self, village_id: int) -> list[VillageName]:
        self._require_village(village_id)
        return self.names.list_for_village(village_id)

    def create(self, village_id: int, data: VillageNameCreate, actor: User) -> VillageName:
        village = self._require_village(village_id)
        self._reject_current_name(village, data.name)
        if data.source_id is not None:
            self._require_source(data.source_id)
        self._reject_duplicate(village_id, data.name, data.name_type)

        item = self.names.add(VillageName(village_id=village_id, **data.model_dump()))
        self.audit.record(actor, "create", "village_name", item.id, {"after": _snapshot(item)})
        self.db.commit()
        return self.names.get(village_id, item.id)

    def update(self, village_id: int, name_id: int, data: VillageNameUpdate, actor: User) -> VillageName:
        village = self._require_village(village_id)
        item = self._get(village_id, name_id)
        changes = data.model_dump(exclude_unset=True)

        if "name" in changes:
            self._reject_current_name(village, changes["name"])
        if changes.get("source_id") is not None and changes["source_id"] != item.source_id:
            self._require_source(changes["source_id"])
        new_name = changes.get("name", item.name)
        new_type = changes.get("name_type", item.name_type)
        if (new_name, new_type) != (item.name, item.name_type):
            self._reject_duplicate(village_id, new_name, new_type, exclude_id=item.id)

        before, after = {}, {}
        for field, new_value in changes.items():
            old_value = getattr(item, field)
            if old_value != new_value:
                before[field], after[field] = old_value, new_value
                setattr(item, field, new_value)
        if not after:
            return item

        self.audit.record(actor, "update", "village_name", item.id, {"before": before, "after": after})
        self.db.commit()
        return self.names.get(village_id, name_id)

    def delete(self, village_id: int, name_id: int, actor: User) -> None:
        self._require_village(village_id)
        item = self._get(village_id, name_id)
        snapshot = _snapshot(item)
        self.names.delete(item)
        self.audit.record(actor, "delete", "village_name", name_id, {"before": snapshot})
        self.db.commit()

    # ---- helpers -----------------------------------------------------
    def _require_village(self, village_id: int) -> Village:
        village = self.villages.get(village_id)
        if not village:
            raise NotFoundError("Village not found")
        return village

    def _get(self, village_id: int, name_id: int) -> VillageName:
        item = self.names.get(village_id, name_id)
        if not item:
            raise NotFoundError("Village name not found")
        return item

    def _require_source(self, source_id: int) -> None:
        if not self.sources.get(source_id):
            raise UnprocessableError(
                "Source does not exist", [{"field": "source_id", "message": "unknown source"}]
            )

    @staticmethod
    def _reject_current_name(village: Village, name: str) -> None:
        current = {(village.name_ar or "").casefold(), (village.name_en or "").casefold()}
        if name.strip().casefold() in current:
            raise UnprocessableError(
                "This is already the village's current name",
                [{"field": "name", "message": "must differ from the current name"}],
            )

    def _reject_duplicate(self, village_id, name, name_type, exclude_id=None) -> None:
        if self.names.find_duplicate(village_id, name, name_type, exclude_id):
            raise ConflictError(
                "This village already has this name with the same type",
                [{"field": "name", "message": "duplicate"}],
            )
