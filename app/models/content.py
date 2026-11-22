from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, declared_attr, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin

LANDMARK_CATEGORIES = (
    "heritage_site", "archaeological_site", "traditional_building", "spring",
    "religious_site", "viewpoint", "other",
)
HERITAGE_CATEGORIES = ("craft", "food", "agricultural_practice", "custom", "other")
ECONOMIC_CATEGORIES = ("crop", "agricultural_product", "livestock", "craft", "industry", "trade", "other")
FACILITY_TYPES = ("school", "clinic", "library", "community_center", "park", "sports_facility", "other")


def _in(column: str, values: tuple[str, ...], name: str) -> CheckConstraint:
    return CheckConstraint(f"{column} IN ({','.join(repr(v) for v in values)})", name=name)


class VillageChildMixin(TimestampMixin):
    """Columns shared by everything that belongs to one village and may cite a source."""

    id: Mapped[int] = mapped_column(primary_key=True)

    @declared_attr
    def village_id(cls) -> Mapped[int]:
        return mapped_column(ForeignKey("villages.id", ondelete="CASCADE"), nullable=False)

    @declared_attr
    def source_id(cls) -> Mapped[int | None]:
        return mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))

    @declared_attr
    def source(cls):
        return relationship("Source")


class HistoricalEvent(VillageChildMixin, Base):
    """Timeline entry. Needs a year and/or a free-text period ("late Ottoman period")."""

    __tablename__ = "historical_events"
    __table_args__ = (
        CheckConstraint("year IS NOT NULL OR date_note IS NOT NULL", name="ck_events_when"),
        Index("ix_events_village_year", "village_id", "year"),
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    year: Mapped[int | None] = mapped_column()
    date_note: Mapped[str | None] = mapped_column(String(100))


class Landmark(VillageChildMixin, Base):
    __tablename__ = "landmarks"
    __table_args__ = (
        _in("category", LANDMARK_CATEGORIES, "ck_landmarks_category"),
        CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_landmarks_coordinates_pair",
        ),
        UniqueConstraint("village_id", "name_ar", name="uq_landmarks_village_name"),
        Index("ix_landmarks_village_category", "village_id", "category"),
    )

    name_ar: Mapped[str] = mapped_column(String(150), nullable=False)
    name_en: Mapped[str | None] = mapped_column(String(150))
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)


class HeritageItem(VillageChildMixin, Base):
    """Traditional crafts, foods, agricultural practices and other cultural characteristics."""

    __tablename__ = "heritage_items"
    __table_args__ = (
        _in("category", HERITAGE_CATEGORIES, "ck_heritage_category"),
        UniqueConstraint("village_id", "name", "category", name="uq_heritage_village_name_category"),
        Index("ix_heritage_village_category", "village_id", "category"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class EconomicItem(VillageChildMixin, Base):
    """Agricultural products, crops, crafts, industries: the village's economic character."""

    __tablename__ = "economic_items"
    __table_args__ = (
        _in("category", ECONOMIC_CATEGORIES, "ck_economic_category"),
        UniqueConstraint("village_id", "name", "category", name="uq_economic_village_name_category"),
        Index("ix_economic_village_category", "village_id", "category"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class Facility(VillageChildMixin, Base):
    """Public facilities as supporting context only (not a service-management system)."""

    __tablename__ = "facilities"
    __table_args__ = (
        _in("facility_type", FACILITY_TYPES, "ck_facilities_type"),
        UniqueConstraint("village_id", "name", "facility_type", name="uq_facilities_village_name_type"),
        Index("ix_facilities_village_type", "village_id", "facility_type"),
    )

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(30), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
