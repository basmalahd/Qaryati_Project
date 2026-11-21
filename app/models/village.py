from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class Village(TimestampMixin, Base):
    __tablename__ = "villages"
    __table_args__ = (
        CheckConstraint(
            "elevation_m IS NULL OR (elevation_m >= -500 AND elevation_m <= 3000)",
            name="ck_villages_elevation_range",
        ),
        CheckConstraint("area_km2 IS NULL OR area_km2 > 0", name="ck_villages_area_positive"),
        Index("ix_villages_name_ar", "name_ar"),
        Index("ix_villages_name_en", "name_en"),
        Index("ix_villages_governorate_id", "governorate_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(150), unique=True, nullable=False)
    name_ar: Mapped[str] = mapped_column(String(150), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(150))
    name_origin: Mapped[str | None] = mapped_column(Text)
    historical_overview: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    elevation_m: Mapped[float | None] = mapped_column(Float)
    area_km2: Mapped[float | None] = mapped_column(Float)
    governorate_id: Mapped[int] = mapped_column(
        ForeignKey("governorates.id", ondelete="RESTRICT"), nullable=False
    )

    governorate: Mapped["Governorate"] = relationship(back_populates="villages")  # noqa: F821
    names: Mapped[list["VillageName"]] = relationship(  # noqa: F821
        back_populates="village", cascade="all, delete-orphan"
    )
    population_records: Mapped[list["PopulationRecord"]] = relationship(  # noqa: F821
        back_populates="village",
        cascade="all, delete-orphan",
        order_by="PopulationRecord.reference_year",
    )
