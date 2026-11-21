from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin

NAME_TYPES = ("alternative_spelling", "transliteration", "former", "historical")


class VillageName(TimestampMixin, Base):
    """Alternative spellings, transliterations, former or historical names."""

    __tablename__ = "village_names"
    __table_args__ = (
        CheckConstraint(
            "name_type IN ('alternative_spelling','transliteration','former','historical')",
            name="ck_village_names_type",
        ),
        UniqueConstraint("village_id", "name", "name_type", name="uq_village_names_unique"),
        Index("ix_village_names_village_id", "village_id"),
        Index("ix_village_names_name", "name"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    village_id: Mapped[int] = mapped_column(
        ForeignKey("villages.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    language: Mapped[str] = mapped_column(String(10), nullable=False, default="ar")
    name_type: Mapped[str] = mapped_column(String(30), nullable=False)
    period_note: Mapped[str | None] = mapped_column(String(200))
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("sources.id", ondelete="SET NULL")
    )

    village: Mapped["Village"] = relationship(back_populates="names")  # noqa: F821
    source: Mapped["Source | None"] = relationship()  # noqa: F821
