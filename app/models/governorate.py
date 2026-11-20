from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Governorate(Base):
    __tablename__ = "governorates"

    id: Mapped[int] = mapped_column(primary_key=True)
    name_ar: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(100), unique=True)

    villages: Mapped[list["Village"]] = relationship(back_populates="governorate")  # noqa: F821
