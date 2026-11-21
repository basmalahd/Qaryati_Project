from sqlalchemy import CheckConstraint, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.models.mixins import TimestampMixin

SOURCE_TYPES = ("book", "census", "official", "website", "article", "oral_history", "other")
_TYPES_SQL = ",".join(f"'{t}'" for t in SOURCE_TYPES)


class Source(TimestampMixin, Base):
    """A reference (book, census, website...) that facts can point to (provenance)."""

    __tablename__ = "sources"
    __table_args__ = (
        CheckConstraint(f"source_type IN ({_TYPES_SQL})", name="ck_sources_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="other")
    author: Mapped[str | None] = mapped_column(String(200))
    url: Mapped[str | None] = mapped_column(String(500))
    publication_year: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str | None] = mapped_column(Text)
