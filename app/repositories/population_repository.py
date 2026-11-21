from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models.population_record import PopulationRecord as PR


class PopulationRepository:
    def __init__(self, db: Session):
        self.db = db

    def list_for_village(
        self, village_id: int, status: str | None, from_year: int | None, to_year: int | None
    ) -> list[PR]:
        conditions = [PR.village_id == village_id]
        if status:
            conditions.append(PR.verification_status == status)
        if from_year is not None:
            conditions.append(PR.reference_year >= from_year)
        if to_year is not None:
            conditions.append(PR.reference_year <= to_year)
        stmt = (
            select(PR)
            .where(*conditions)
            .options(joinedload(PR.source))
            .order_by(PR.reference_year, PR.id)
        )
        return list(self.db.scalars(stmt).unique())

    def get(self, village_id: int, record_id: int) -> PR | None:
        stmt = (
            select(PR)
            .where(PR.id == record_id, PR.village_id == village_id)
            .options(joinedload(PR.source))
            .execution_options(populate_existing=True)
        )
        return self.db.scalars(stmt).unique().one_or_none()

    def find_duplicate(
        self, village_id: int, year: int, source_id: int, exclude_id: int | None = None
    ) -> PR | None:
        stmt = select(PR).where(
            PR.village_id == village_id, PR.reference_year == year, PR.source_id == source_id
        )
        if exclude_id is not None:
            stmt = stmt.where(PR.id != exclude_id)
        return self.db.scalars(stmt).first()

    def conflict_years(self, village_id: int) -> set[int]:
        """Years where different records report different population values."""
        rows = self.db.execute(
            select(PR.reference_year)
            .where(PR.village_id == village_id)
            .group_by(PR.reference_year)
            .having(func.count(func.distinct(PR.population)) > 1)
        )
        return {r[0] for r in rows}

    def has_conflict(self, village_id: int, year: int) -> bool:
        distinct_values = self.db.scalar(
            select(func.count(func.distinct(PR.population))).where(
                PR.village_id == village_id, PR.reference_year == year
            )
        )
        return (distinct_values or 0) > 1

    def add(self, record: PR) -> PR:
        self.db.add(record)
        self.db.flush()
        return record

    def delete(self, record: PR) -> None:
        self.db.delete(record)
        self.db.flush()
