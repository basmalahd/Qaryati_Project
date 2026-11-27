from sqlalchemy import func, select, text
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

    # ---- reads (native SQL) -----------------------------------------
    def latest_per_village(self, governorate_id: int | None, limit: int) -> list[dict]:
        """Most recent usable population record of every village, in native SQL.

        Written as raw SQL on purpose (the project requires native-SQL cases): a window
        function picks one row per village, which is awkward to express in the ORM.
        Ranking: newest year first, then verified > pending, then newest record id.
        Disputed records are ignored. Villages without any usable record are left out.
        Only the optional filter is assembled in Python; every value is a bound parameter.
        """
        params: dict = {"limit": limit}
        governorate_filter = ""
        if governorate_id is not None:
            governorate_filter = "AND v.governorate_id = :governorate_id"
            params["governorate_id"] = governorate_id

        rows = self.db.execute(
            text(
                f"""
                SELECT v.id AS village_id,
                       v.name_ar,
                       v.name_en,
                       v.governorate_id,
                       p.population,
                       p.reference_year,
                       p.verification_status,
                       p.source_id
                FROM villages v
                JOIN (
                    SELECT pr.village_id,
                           pr.population,
                           pr.reference_year,
                           pr.verification_status,
                           pr.source_id,
                           ROW_NUMBER() OVER (
                               PARTITION BY pr.village_id
                               ORDER BY pr.reference_year DESC,
                                        CASE pr.verification_status
                                             WHEN 'verified' THEN 0 ELSE 1 END,
                                        pr.id DESC
                           ) AS rn
                    FROM population_records pr
                    WHERE pr.verification_status <> 'disputed'
                ) p ON p.village_id = v.id AND p.rn = 1
                WHERE 1 = 1 {governorate_filter}
                ORDER BY p.population DESC, v.name_ar
                LIMIT :limit
                """  # noqa: S608 - the only interpolated part is a fixed literal clause
            ),
            params,
        ).mappings()
        return [dict(r) for r in rows]
