import math

from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.models.user import User
from app.models.village import Village
from app.repositories.governorate_repository import GovernorateRepository
from app.repositories.village_repository import VillageRepository
from app.schemas.village import VillageCreate, VillageUpdate
from app.services.audit_service import AuditService

_FIELDS = (
    "slug", "name_ar", "name_en", "name_origin", "historical_overview",
    "latitude", "longitude", "governorate_id",
)


def _snapshot(v: Village) -> dict:
    return {"id": v.id, **{f: getattr(v, f) for f in _FIELDS}}


class VillageService:
    """Business rules for villages. One public method = one transaction."""

    def __init__(self, db: Session):
        self.db = db
        self.villages = VillageRepository(db)
        self.governorates = GovernorateRepository(db)
        self.audit = AuditService(db)

    # ---- queries -----------------------------------------------------
    def search(self, q, governorate_id, sort, order, page, page_size) -> dict:
        items, total = self.villages.search(q, governorate_id, sort, order, page, page_size)
        return {
            "items": items,
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": math.ceil(total / page_size) if total else 0,
        }

    def get(self, village_id: int) -> Village:
        village = self.villages.get_detail(village_id)
        if not village:
            raise NotFoundError("Village not found")
        return village

    def stats_by_governorate(self) -> list[dict]:
        return self.villages.count_by_governorate()

    # ---- commands ----------------------------------------------------
    def create(self, data: VillageCreate, actor: User) -> Village:
        self._require_governorate(data.governorate_id)
        if self.villages.get_by_slug(data.slug):
            raise ConflictError(
                "A village with this slug already exists",
                [{"field": "slug", "message": "already in use"}],
            )
        village = self.villages.add(Village(**data.model_dump()))
        self.audit.record(actor, "create", "village", village.id, {"after": _snapshot(village)})
        self.db.commit()  # village + audit entry are atomic
        return self.get(village.id)

    def update(self, village_id: int, data: VillageUpdate, actor: User) -> Village:
        village = self.get(village_id)
        changes = data.model_dump(exclude_unset=True)

        if "governorate_id" in changes and changes["governorate_id"] != village.governorate_id:
            self._require_governorate(changes["governorate_id"])
        if "slug" in changes and changes["slug"] != village.slug:
            if self.villages.get_by_slug(changes["slug"]):
                raise ConflictError(
                    "A village with this slug already exists",
                    [{"field": "slug", "message": "already in use"}],
                )

        lat = changes.get("latitude", village.latitude)
        lon = changes.get("longitude", village.longitude)
        if (lat is None) != (lon is None):
            raise UnprocessableError(
                "latitude and longitude must be provided together",
                [{"field": "latitude", "message": "must be set together with longitude"}],
            )

        before, after = {}, {}
        for field, new_value in changes.items():
            old_value = getattr(village, field)
            if old_value != new_value:
                before[field], after[field] = old_value, new_value
                setattr(village, field, new_value)

        if not after:  # nothing really changed: no write, no audit noise
            return village

        self.audit.record(actor, "update", "village", village.id, {"before": before, "after": after})
        self.db.commit()
        return self.get(village_id)

    def delete(self, village_id: int, actor: User) -> None:
        village = self.get(village_id)
        snapshot = _snapshot(village)
        self.villages.delete(village)
        self.audit.record(actor, "delete", "village", village_id, {"before": snapshot})
        self.db.commit()

    # ---- helpers -----------------------------------------------------
    def _require_governorate(self, governorate_id: int) -> None:
        if not self.governorates.get(governorate_id):
            raise UnprocessableError(
                "Governorate does not exist",
                [{"field": "governorate_id", "message": "unknown governorate"}],
            )
