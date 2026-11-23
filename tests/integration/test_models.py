import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import Base
from app.models import Governorate, PopulationRecord, Source, Village


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def village_and_source(db):
    gov = Governorate(name_ar="قلقيلية", name_en="Qalqilya")
    src = Source(title="PCBS Census 1997", source_type="census")
    db.add_all([gov, src])
    db.flush()
    v = Village(slug="jinsafut", name_ar="جينصافوط", governorate_id=gov.id)
    db.add(v)
    db.commit()
    return v, src


def test_population_history_is_ordered_by_year(db, village_and_source):
    v, src = village_and_source
    db.add_all([
        PopulationRecord(village_id=v.id, population=3000, reference_year=2007, source_id=src.id),
        PopulationRecord(village_id=v.id, population=2000, reference_year=1997, source_id=src.id),
    ])
    db.commit()
    db.refresh(v)
    assert [r.reference_year for r in v.population_records] == [1997, 2007]


def test_negative_population_rejected(db, village_and_source):
    v, src = village_and_source
    db.add(PopulationRecord(village_id=v.id, population=-5, reference_year=2000, source_id=src.id,
                            verification_status="pending"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_same_source_same_year_rejected_but_other_source_allowed(db, village_and_source):
    v, src = village_and_source
    other = Source(title="Local council 2007", source_type="official")
    db.add(other)
    db.flush()
    db.add(PopulationRecord(village_id=v.id, population=100, reference_year=2007,
                            source_id=src.id, verification_status="pending"))
    db.add(PopulationRecord(village_id=v.id, population=120, reference_year=2007,
                            source_id=other.id, verification_status="pending"))
    db.commit()  # conflicting values from different sources are both kept

    db.add(PopulationRecord(village_id=v.id, population=999, reference_year=2007,
                            source_id=src.id, verification_status="pending"))
    with pytest.raises(IntegrityError):
        db.commit()
