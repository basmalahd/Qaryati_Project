from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.governorate import Governorate


class GovernorateRepository:
    def __init__(self, db: Session):
        self.db = db

    def get(self, governorate_id: int) -> Governorate | None:
        return self.db.get(Governorate, governorate_id)

    def get_by_name_ar(self, name_ar: str) -> Governorate | None:
        return self.db.scalar(select(Governorate).where(Governorate.name_ar == name_ar))

    def list_all(self) -> list[Governorate]:
        return list(self.db.scalars(select(Governorate).order_by(Governorate.name_ar)))

    def add(self, governorate: Governorate) -> Governorate:
        self.db.add(governorate)
        self.db.flush()
        return governorate
