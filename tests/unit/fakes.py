"""In-memory stand-ins so services can be unit-tested without a database."""
from types import SimpleNamespace
from unittest.mock import MagicMock

USER = SimpleNamespace(id=7)
SOURCE = SimpleNamespace(id=1, title="PCBS Census", source_type="census", publication_year=1997)


def make_db(calls: list) -> MagicMock:
    """A fake session that records commits on a shared timeline."""
    db = MagicMock()
    db.commit.side_effect = lambda: calls.append("commit")
    return db


class FakeAudit:
    def __init__(self, calls: list):
        self.calls = calls
        self.entries: list[tuple] = []

    def record(self, actor, action, entity_type, entity_id, changes):
        self.calls.append("audit")
        self.entries.append((action, entity_type, entity_id, changes))


class FakeVillages:
    def get(self, village_id):
        return SimpleNamespace(id=village_id) if village_id == 1 else None


class FakeSources:
    def get(self, source_id):
        return SOURCE if source_id == 1 else None
