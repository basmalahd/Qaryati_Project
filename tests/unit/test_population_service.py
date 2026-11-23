from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.schemas.population import PopulationCreate, PopulationUpdate
from app.services.population_service import PopulationService
from tests.unit.fakes import SOURCE, USER, FakeAudit, FakeSources, FakeVillages, make_db

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


class FakeRecords:
    def __init__(self, calls):
        self.calls = calls
        self.rows: dict[int, SimpleNamespace] = {}
        self._next = 100

    def add(self, record):
        record.id = self._next
        self._next += 1
        self.rows[record.id] = SimpleNamespace(
            id=record.id, village_id=record.village_id, population=record.population,
            reference_year=record.reference_year, source_id=record.source_id,
            verification_status=record.verification_status, notes=record.notes,
            source=SOURCE, created_at=NOW, updated_at=NOW,
        )
        self.calls.append("insert")
        return record

    def get(self, village_id, record_id):
        row = self.rows.get(record_id)
        return row if row and row.village_id == village_id else None

    def find_duplicate(self, village_id, year, source_id, exclude_id=None):
        for r in self.rows.values():
            if (r.village_id, r.reference_year, r.source_id) == (village_id, year, source_id) \
                    and r.id != exclude_id:
                return r
        return None

    def has_conflict(self, village_id, year):
        return len({r.population for r in self.rows.values()
                    if r.village_id == village_id and r.reference_year == year}) > 1

    def conflict_years(self, village_id):
        years = {r.reference_year for r in self.rows.values() if r.village_id == village_id}
        return {y for y in years if self.has_conflict(village_id, y)}

    def list_for_village(self, village_id, status, from_year, to_year):
        rows = [r for r in self.rows.values() if r.village_id == village_id]
        return sorted(rows, key=lambda r: (r.reference_year, r.id))

    def delete(self, record):
        del self.rows[record.id]
        self.calls.append("delete")


def row(id=1, year=1997, population=1000, status="pending", source_id=1):
    return SimpleNamespace(id=id, village_id=1, population=population, reference_year=year,
                           source_id=source_id, verification_status=status, notes=None,
                           source=SOURCE, created_at=NOW, updated_at=NOW)


def make_service(*rows):
    calls: list[str] = []
    service = PopulationService(make_db(calls))
    service.records = FakeRecords(calls)
    service.villages, service.sources = FakeVillages(), FakeSources()
    service.audit = FakeAudit(calls)
    for r in rows:
        service.records.rows[r.id] = r
    return service, calls


def create_data(**kw):
    return PopulationCreate(**{"population": 100, "reference_year": 2000, "source_id": 1, **kw})


def test_create_audits_before_a_single_commit():
    service, calls = make_service()
    result = service.create(1, create_data(), USER)

    assert calls == ["insert", "audit", "commit"]  # data and audit share one transaction
    assert result.verification_status == "pending"
    assert service.audit.entries[0][:2] == ("create", "population_record")


@pytest.mark.parametrize("village_id, data, error", [
    (99, {}, NotFoundError),                       # unknown village
    (1, {"source_id": 2}, UnprocessableError),     # unknown source: provenance is mandatory
    (1, {"reference_year": 1997}, ConflictError),  # same source already reported 1997
])
def test_rejected_create_writes_nothing(village_id, data, error):
    service, calls = make_service(row(year=1997, source_id=1))
    with pytest.raises(error):
        service.create(village_id, create_data(**data), USER)
    assert calls == []  # no insert, no audit entry, no commit


def test_verified_record_is_locked():
    service, calls = make_service(row(status="verified"))
    with pytest.raises(ConflictError):
        service.update(1, 1, PopulationUpdate(population=1200), USER)
    assert calls == []


def test_editing_a_disputed_record_sends_it_back_to_pending():
    service, calls = make_service(row(status="disputed"))
    service.update(1, 1, PopulationUpdate(population=1200), USER)

    assert calls == ["audit", "commit"]
    assert service.audit.entries[0][3] == {
        "before": {"population": 1000, "verification_status": "disputed"},
        "after": {"population": 1200, "verification_status": "pending"},
    }


def test_update_that_changes_nothing_writes_nothing():
    service, calls = make_service(row())
    service.update(1, 1, PopulationUpdate(population=1000), USER)
    assert calls == []


def test_update_cannot_duplicate_another_record_of_the_same_source():
    service, _ = make_service(row(id=1, year=1997), row(id=2, year=2007))
    with pytest.raises(ConflictError):
        service.update(1, 1, PopulationUpdate(reference_year=2007), USER)


def test_status_change_is_audited_and_repeating_it_is_a_noop():
    service, calls = make_service(row())
    service.set_status(1, 1, "verified", USER)
    assert calls == ["audit", "commit"]
    assert service.audit.entries[0][3] == {"before": {"verification_status": "pending"},
                                           "after": {"verification_status": "verified"}}

    calls.clear()
    service.set_status(1, 1, "verified", USER)
    assert calls == []


def test_delete_keeps_a_snapshot_in_the_audit_entry():
    service, calls = make_service(row(population=1000))
    service.delete(1, 1, USER)
    assert calls == ["delete", "audit", "commit"]
    action, _, entity_id, changes = service.audit.entries[0]
    assert (action, entity_id, changes["before"]["population"]) == ("delete", 1, 1000)


def test_history_flags_conflicting_values_for_the_same_year():
    service, _ = make_service(
        row(id=1, year=1997, population=1000), row(id=2, year=2007, population=2000),
        row(id=3, year=2007, population=2200, source_id=2),
    )
    flags = [(r.reference_year, r.has_conflict) for r in service.history(1, None, None, None)]
    assert flags == [(1997, False), (2007, True), (2007, True)]


def test_history_rejects_an_inverted_year_range():
    service, _ = make_service()
    with pytest.raises(UnprocessableError):
        service.history(1, None, 2010, 2000)
