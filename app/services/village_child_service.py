from typing import Any

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.models.user import User
from app.repositories.source_repository import SourceRepository
from app.repositories.village_child_repository import VillageChildRepository
from app.repositories.village_repository import VillageRepository
from app.services.audit_service import AuditService

_NOT_AUDITED = {"created_at", "updated_at"}


class VillageChildService:
    """Generic CRUD rules for content that belongs to a village.

    One implementation of: village must exist -> cited source must exist -> state validation ->
    duplicate check -> write + audit entry in ONE transaction -> re-read with eager loading.
    Subclasses only declare what is specific (model, unique keys, ordering, extra validation).
    """

    model: type
    entity_type: str
    label: str = "Item"
    unique_keys: tuple[str, ...] = ()

    def __init__(self, db: Session):
        self.db = db
        self.repo = VillageChildRepository(db, self.model)
        self.villages = VillageRepository(db)
        self.sources = SourceRepository(db)
        self.audit = AuditService(db)
        self._audited = [c for c in self.model.__table__.columns.keys() if c not in _NOT_AUDITED]

    # ---- hooks for subclasses ----------------------------------------
    def ordering(self) -> list:
        return [self.model.id]

    def validate_state(self, state: dict[str, Any]) -> None:
        """Cross-field business rules, applied to the full state after a create/update."""

    # ---- queries -----------------------------------------------------
    def _list(self, village_id: int, filters: dict | None = None, extra: list | None = None):
        self._require_village(village_id)
        return self.repo.list_for_village(village_id, filters, extra, self.ordering())

    # ---- commands ----------------------------------------------------
    def create(self, village_id: int, data, actor: User):
        self._require_village(village_id)
        values = data.model_dump()
        self.validate_state(values)
        self._require_source(values.get("source_id"))
        self._reject_duplicate(village_id, values)

        item = self.repo.add(self.model(village_id=village_id, **values))
        self.audit.record(actor, "create", self.entity_type, item.id, {"after": self._snapshot(item)})
        self.db.commit()
        return self.repo.get(village_id, item.id)

    def update(self, village_id: int, item_id: int, data, actor: User):
        item = self._get(village_id, item_id)
        changes = data.model_dump(exclude_unset=True)
        merged = {**self._snapshot(item), **changes}
        self.validate_state(merged)

        if changes.get("source_id") is not None and changes["source_id"] != item.source_id:
            self._require_source(changes["source_id"])
        if any(getattr(item, k) != merged[k] for k in self.unique_keys):
            self._reject_duplicate(village_id, merged, exclude_id=item.id)

        before, after = {}, {}
        for field, new_value in changes.items():
            old_value = getattr(item, field)
            if old_value != new_value:
                before[field], after[field] = old_value, new_value
                setattr(item, field, new_value)
        if not after:
            return item

        self.audit.record(actor, "update", self.entity_type, item.id, {"before": before, "after": after})
        self.db.commit()
        return self.repo.get(village_id, item_id)

    def delete(self, village_id: int, item_id: int, actor: User) -> None:
        item = self._get(village_id, item_id)
        snapshot = self._snapshot(item)
        self.repo.delete(item)
        self.audit.record(actor, "delete", self.entity_type, item_id, {"before": snapshot})
        self.db.commit()

    # ---- helpers -----------------------------------------------------
    def _snapshot(self, item) -> dict[str, Any]:
        return {c: getattr(item, c) for c in self._audited}

    def _require_village(self, village_id: int) -> None:
        if not self.villages.get(village_id):
            raise NotFoundError("Village not found")

    def _get(self, village_id: int, item_id: int):
        self._require_village(village_id)
        item = self.repo.get(village_id, item_id)
        if not item:
            raise NotFoundError(f"{self.label} not found")
        return item

    def _require_source(self, source_id: int | None) -> None:
        if source_id is not None and not self.sources.get(source_id):
            raise UnprocessableError(
                "Source does not exist", [{"field": "source_id", "message": "unknown source"}]
            )

    def _reject_duplicate(self, village_id: int, values: dict, exclude_id: int | None = None) -> None:
        if not self.unique_keys:
            return
        keys = {k: values[k] for k in self.unique_keys}
        if self.repo.find_duplicate(village_id, keys, exclude_id):
            raise ConflictError(
                f"{self.label} already exists for this village",
                [{"field": self.unique_keys[0], "message": "duplicate"}],
            )
