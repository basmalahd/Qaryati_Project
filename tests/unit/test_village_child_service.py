import pytest

from app.core.errors import ConflictError, NotFoundError, UnprocessableError
from app.models.content import HistoricalEvent, Landmark
from app.schemas.content import EventUpdate, LandmarkCreate, LandmarkUpdate
from app.services.village_content_service import EventService, LandmarkService
from tests.unit.fakes import USER, FakeAudit, FakeSources, FakeVillages, make_db


class FakeRepo:
    def __init__(self, calls):
        self.calls = calls
        self.items = {}
        self._next = 100

    def add(self, item):
        item.id = self._next
        self._next += 1
        self.items[item.id] = item
        self.calls.append("insert")
        return item

    def get(self, village_id, item_id):
        item = self.items.get(item_id)
        return item if item and item.village_id == village_id else None

    def find_duplicate(self, village_id, keys, exclude_id=None):
        for it in self.items.values():
            if it.village_id == village_id and it.id != exclude_id \
                    and all(getattr(it, k) == v for k, v in keys.items()):
                return it
        return None

    def delete(self, item):
        del self.items[item.id]
        self.calls.append("delete")


def build(service_cls, *seed):
    calls: list[str] = []
    service = service_cls(make_db(calls))
    service.repo, service.audit = FakeRepo(calls), FakeAudit(calls)
    service.villages, service.sources = FakeVillages(), FakeSources()
    for item in seed:
        service.repo.items[item.id] = item
    return service, calls


def landmark(**kw):
    values = dict(id=1, village_id=1, name_ar="عين الماء", name_en=None, category="spring",
                  description=None, latitude=None, longitude=None, source_id=None)
    return Landmark(**{**values, **kw})


def new_landmark(**kw):
    return LandmarkCreate(**{"name_ar": "المقام", "category": "religious_site", **kw})


def test_create_audits_before_a_single_commit_and_skips_timestamps():
    service, calls = build(LandmarkService)
    service.create(1, new_landmark(), USER)

    assert calls == ["insert", "audit", "commit"]
    after = service.audit.entries[0][3]["after"]
    assert after["name_ar"] == "المقام"
    assert "created_at" not in after and "updated_at" not in after


@pytest.mark.parametrize("village_id, data, error", [
    (99, {}, NotFoundError),
    (1, {"source_id": 2}, UnprocessableError),
    (1, {"name_ar": "عين الماء"}, ConflictError),  # unique key (village, name_ar)
])
def test_rejected_create_writes_nothing(village_id, data, error):
    service, calls = build(LandmarkService, landmark())
    with pytest.raises(error):
        service.create(village_id, new_landmark(**data), USER)
    assert calls == []


def test_coordinates_must_stay_a_pair_after_an_update():
    service, calls = build(LandmarkService, landmark(latitude=32.1, longitude=35.0))
    with pytest.raises(UnprocessableError):
        service.update(1, 1, LandmarkUpdate(latitude=None), USER)  # would leave only longitude
    assert calls == []

    service.update(1, 1, LandmarkUpdate(latitude=None, longitude=None), USER)
    assert service.audit.entries[0][3] == {"before": {"latitude": 32.1, "longitude": 35.0},
                                           "after": {"latitude": None, "longitude": None}}


def test_renaming_into_an_existing_entry_is_a_conflict():
    service, _ = build(LandmarkService, landmark(id=1), landmark(id=2, name_ar="المقام"))
    with pytest.raises(ConflictError):
        service.update(1, 2, LandmarkUpdate(name_ar="عين الماء"), USER)


def test_unknown_item_is_not_found():
    service, _ = build(LandmarkService)
    with pytest.raises(NotFoundError):
        service.update(1, 5, LandmarkUpdate(description="x"), USER)


def test_update_without_changes_writes_nothing():
    service, calls = build(LandmarkService, landmark())
    service.update(1, 1, LandmarkUpdate(category="spring"), USER)
    assert calls == []


def test_delete_audits_a_snapshot_then_commits():
    service, calls = build(LandmarkService, landmark())
    service.delete(1, 1, USER)
    assert calls == ["delete", "audit", "commit"]
    assert service.audit.entries[0][3]["before"]["name_ar"] == "عين الماء"


def test_event_needs_a_year_or_a_period():
    service, _ = build(EventService)
    with pytest.raises(UnprocessableError):
        service.validate_state({"year": None, "date_note": None})
    service.validate_state({"year": 1900, "date_note": None})
    service.validate_state({"year": None, "date_note": "Ottoman period"})


def test_clearing_the_only_time_information_of_an_event_is_rejected():
    event = HistoricalEvent(id=1, village_id=1, title="Founded", year=1900, date_note=None,
                            description=None, source_id=None)
    service, calls = build(EventService, event)
    with pytest.raises(UnprocessableError):
        service.update(1, 1, EventUpdate(year=None), USER)
    assert calls == []
