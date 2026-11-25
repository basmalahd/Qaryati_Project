from sqlalchemy.orm import Session

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.models.population_record import PopulationRecord
from app.models.user import User
from app.repositories.population_repository import PopulationRepository
from app.repositories.source_repository import SourceRepository
from app.repositories.village_repository import VillageRepository
from app.schemas.population import PopulationCreate, PopulationRead, PopulationUpdate
from app.services.audit_service import AuditService

_FIELDS = (
    "village_id", "population", "reference_year", "source_id", "verification_status", "notes",
)


def _snapshot(r: PopulationRecord) -> dict:
    return {"id": r.id, **{f: getattr(r, f) for f in _FIELDS}}


class PopulationService:
    """Rules for population history (see docs/adr/005-population-records.md).

    1. Every record cites a source.            4. Different sources may disagree: both kept, flagged.
    2. Year must not be in the future.          5. Verified records are locked until disputed.
    3. One value per (village, year, source).   6. Any edit sends a record back to 'pending'.
    """

    def __init__(self, db: Session):
        self.db = db
        self.records = PopulationRepository(db)
        self.villages = VillageRepository(db)
        self.sources = SourceRepository(db)
        self.audit = AuditService(db)

    # ---- queries -----------------------------------------------------
    def history(self, village_id, status, from_year, to_year) -> list[PopulationRead]:
        self._require_village(village_id)
        if from_year is not None and to_year is not None and from_year > to_year:
            raise UnprocessableError(
                "from_year must not be after to_year",
                [{"field": "from_year", "message": "must be <= to_year"}],
            )
        records = self.records.list_for_village(village_id, status, from_year, to_year)
        # computed over *all* records, so filtering by status can't hide a conflict
        conflicts = self.records.conflict_years(village_id)
        return [
            PopulationRead.model_validate(r).model_copy(
                update={"has_conflict": r.reference_year in conflicts}
            )
            for r in records
        ]

    # ---- commands ----------------------------------------------------
    def create(self, village_id: int, data: PopulationCreate, actor: User) -> PopulationRead:
        self._require_village(village_id)
        self._require_source(data.source_id)
        self._reject_duplicate(village_id, data.reference_year, data.source_id)

        record = self.records.add(
            PopulationRecord(
                village_id=village_id,
                population=data.population,
                reference_year=data.reference_year,
                source_id=data.source_id,
                verification_status="pending",
                notes=data.notes,
            )
        )
        self.audit.record(actor, "create", "population_record", record.id, {"after": _snapshot(record)})
        self.db.commit()
        return self._read(village_id, record.id)

    def update(
        self, village_id: int, record_id: int, data: PopulationUpdate, actor: User
    ) -> PopulationRead:
        record = self._get_record(village_id, record_id)
        if record.verification_status == "verified":
            raise ConflictError(
                "Verified records are locked; a verifier must mark it as disputed first",
                [{"field": "verification_status", "message": "record is verified"}],
            )

        changes = data.model_dump(exclude_unset=True)
        if "source_id" in changes and changes["source_id"] != record.source_id:
            self._require_source(changes["source_id"])
        new_year = changes.get("reference_year", record.reference_year)
        new_source = changes.get("source_id", record.source_id)
        if (new_year, new_source) != (record.reference_year, record.source_id):
            self._reject_duplicate(village_id, new_year, new_source, exclude_id=record.id)

        before, after = {}, {}
        for field, new_value in changes.items():
            old_value = getattr(record, field)
            if old_value != new_value:
                before[field], after[field] = old_value, new_value
                setattr(record, field, new_value)
        if not after:
            return self._read(village_id, record_id)

        if record.verification_status != "pending":  # e.g. 'disputed' -> needs fresh review
            before["verification_status"] = record.verification_status
            after["verification_status"] = "pending"
            record.verification_status = "pending"

        self.audit.record(actor, "update", "population_record", record.id,
                          {"before": before, "after": after})
        self.db.commit()
        return self._read(village_id, record_id)

    def set_status(self, village_id: int, record_id: int, status: str, actor: User) -> PopulationRead:
        record = self._get_record(village_id, record_id)
        if record.verification_status == status:
            return self._read(village_id, record_id)
        self.audit.record(
            actor, "update", "population_record", record.id,
            {"before": {"verification_status": record.verification_status},
             "after": {"verification_status": status}},
        )
        record.verification_status = status
        self.db.commit()
        return self._read(village_id, record_id)

    def delete(self, village_id: int, record_id: int, actor: User) -> None:
        record = self._get_record(village_id, record_id)
        snapshot = _snapshot(record)
        self.records.delete(record)
        self.audit.record(actor, "delete", "population_record", record_id, {"before": snapshot})
        self.db.commit()

    # ---- helpers -----------------------------------------------------
    def _require_village(self, village_id: int) -> None:
        if not self.villages.get(village_id):
            raise NotFoundError("Village not found")

    def _require_source(self, source_id: int) -> None:
        if not self.sources.get(source_id):
            raise UnprocessableError(
                "Source does not exist", [{"field": "source_id", "message": "unknown source"}]
            )

    def _reject_duplicate(self, village_id, year, source_id, exclude_id=None) -> None:
        if self.records.find_duplicate(village_id, year, source_id, exclude_id):
            raise ConflictError(
                "This source already has a record for this village and year",
                [{"field": "reference_year", "message": "duplicate for this source"}],
            )

    def _get_record(self, village_id: int, record_id: int) -> PopulationRecord:
        self._require_village(village_id)
        record = self.records.get(village_id, record_id)
        if not record:
            raise NotFoundError("Population record not found")
        return record

    def _read(self, village_id: int, record_id: int) -> PopulationRead:
        record = self.records.get(village_id, record_id)
        return PopulationRead.model_validate(record).model_copy(
            update={"has_conflict": self.records.has_conflict(village_id, record.reference_year)}
        )

    # ---- queries -----------------------------------------------------
    def latest_per_village(self, governorate_id: int | None, limit: int) -> list[dict]:
        return self.records.latest_per_village(governorate_id, limit)
