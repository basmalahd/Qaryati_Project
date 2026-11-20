from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin


class PopulationRecord(TimestampMixin, Base):
    """Population is history, not one number. Every record MUST cite a source.

    Conflict strategy: two different sources may report different values for
    the same year (both kept, nothing overwritten). The same source cannot
    report the same year twice for the same village.
    """

    __tablename__ = "population_records"
    __table_args__ = (
        CheckConstraint("population >= 0", name="ck_population_non_negative"),
        CheckConstraint(
            "reference_year BETWEEN 1800 AND 2100", name="ck_population_year_range"
        ),
        CheckConstraint(
            "verification_status IN ('pending','verified','disputed')",
            name="ck_population_status",
        ),
        UniqueConstraint(
            "village_id", "reference_year", "source_id", name="uq_population_village_year_source"
        ),
        Index("ix_population_village_year", "village_id", "reference_year"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    village_id: Mapped[int] = mapped_column(
        ForeignKey("villages.id", ondelete="CASCADE"), nullable=False
    )
    population: Mapped[int] = mapped_column(nullable=False)
    reference_year: Mapped[int] = mapped_column(nullable=False)
    source_id: Mapped[int] = mapped_column(
        ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False
    )
    verification_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending"
    )
    notes: Mapped[str | None] = mapped_column(Text)

    village: Mapped["Village"] = relationship(back_populates="population_records")  # noqa: F821
