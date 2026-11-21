from sqlalchemy import exists, func, or_, select, text
from sqlalchemy.orm import Session, joinedload, selectinload

from app.models.village import Village
from app.models.village_name import VillageName
from app.repositories.utils import escape_like

SORTABLE = {
    "id": Village.id,
    "name_ar": Village.name_ar,
    "name_en": Village.name_en,
    "created_at": Village.created_at,
}


class VillageRepository:
    def __init__(self, db: Session):
        self.db = db

    # ---- reads (ORM) -------------------------------------------------
    def get_detail(self, village_id: int) -> Village | None:
        stmt = (
            select(Village)
            .where(Village.id == village_id)
            .options(joinedload(Village.governorate), selectinload(Village.names))
            .execution_options(populate_existing=True)
        )
        return self.db.scalars(stmt).unique().one_or_none()

    def get(self, village_id: int) -> Village | None:
        return self.db.get(Village, village_id)

    def get_by_slug(self, slug: str) -> Village | None:
        return self.db.scalar(select(Village).where(Village.slug == slug))

    def search(
        self,
        q: str | None,
        governorate_id: int | None,
        sort: str,
        order: str,
        page: int,
        page_size: int,
    ) -> tuple[list[Village], int]:
        conditions = []
        if q:
            pattern = f"%{escape_like(q.strip())}%"
            alt_name_match = exists().where(
                VillageName.village_id == Village.id,
                VillageName.name.ilike(pattern, escape="\\"),
            )
            conditions.append(
                or_(
                    Village.name_ar.ilike(pattern, escape="\\"),
                    Village.name_en.ilike(pattern, escape="\\"),
                    alt_name_match,
                )
            )
        if governorate_id is not None:
            conditions.append(Village.governorate_id == governorate_id)

        total = self.db.scalar(select(func.count(Village.id)).where(*conditions)) or 0

        column = SORTABLE[sort]
        ordering = column.desc() if order == "desc" else column.asc()
        stmt = (
            select(Village)
            .where(*conditions)
            # joinedload (many-to-one) avoids an N+1 query when rendering the governorate
            .options(joinedload(Village.governorate))
            .order_by(ordering, Village.id)  # id = stable tie-breaker for pagination
            .limit(page_size)
            .offset((page - 1) * page_size)
        )
        return list(self.db.scalars(stmt).unique()), total

    # ---- reads (native SQL) -----------------------------------------
    def count_by_governorate(self) -> list[dict]:
        """Aggregation written as native SQL on purpose (project requires raw SQL cases)."""
        rows = self.db.execute(
            text(
                """
                SELECT g.id AS governorate_id,
                       g.name_ar,
                       g.name_en,
                       COUNT(v.id) AS village_count
                FROM governorates g
                LEFT JOIN villages v ON v.governorate_id = g.id
                GROUP BY g.id, g.name_ar, g.name_en
                ORDER BY village_count DESC, g.name_ar
                """
            )
        ).mappings()
        return [dict(r) for r in rows]

    # ---- writes ------------------------------------------------------
    def add(self, village: Village) -> Village:
        self.db.add(village)
        self.db.flush()
        return village

    def delete(self, village: Village) -> None:
        self.db.delete(village)
        self.db.flush()
