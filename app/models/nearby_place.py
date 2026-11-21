from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
from app.models.mixins import TimestampMixin

RELATION_TYPES = ("borders", "nearby", "nearest_city")
DIRECTIONS = ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
_REL_SQL = ",".join(f"'{t}'" for t in RELATION_TYPES)
_DIR_SQL = ",".join(f"'{d}'" for d in DIRECTIONS)


class NearbyPlace(TimestampMixin, Base):
    """A geographic relation seen from one village's point of view.

    The target is EITHER another village of the platform (`related_village_id`) OR a free-text
    place such as a city that is not modelled (`place_name`) - never both, never neither.
    Relations are directional on purpose (no hidden reverse writes).
    """

    __tablename__ = "nearby_places"
    __table_args__ = (
        CheckConstraint(f"relation_type IN ({_REL_SQL})", name="ck_nearby_relation_type"),
        CheckConstraint(f"direction IS NULL OR direction IN ({_DIR_SQL})", name="ck_nearby_direction"),
        CheckConstraint(
            "(related_village_id IS NOT NULL AND place_name IS NULL) OR "
            "(related_village_id IS NULL AND place_name IS NOT NULL)",
            name="ck_nearby_exactly_one_target",
        ),
        CheckConstraint(
            "related_village_id IS NULL OR related_village_id <> village_id",
            name="ck_nearby_not_self",
        ),
        CheckConstraint("distance_km IS NULL OR distance_km >= 0", name="ck_nearby_distance"),
        Index("ix_nearby_village_id", "village_id"),
        Index(
            "uq_nearby_village_rel", "village_id", "related_village_id", "relation_type",
            unique=True,
            postgresql_where=text("related_village_id IS NOT NULL"),
            sqlite_where=text("related_village_id IS NOT NULL"),
        ),
        Index(
            "uq_nearby_place_rel", "village_id", "place_name", "relation_type",
            unique=True,
            postgresql_where=text("place_name IS NOT NULL"),
            sqlite_where=text("place_name IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    village_id: Mapped[int] = mapped_column(
        ForeignKey("villages.id", ondelete="CASCADE"), nullable=False
    )
    related_village_id: Mapped[int | None] = mapped_column(
        ForeignKey("villages.id", ondelete="CASCADE")
    )
    place_name: Mapped[str | None] = mapped_column(String(150))
    relation_type: Mapped[str] = mapped_column(String(20), nullable=False)
    distance_km: Mapped[float | None] = mapped_column(Float)
    direction: Mapped[str | None] = mapped_column(String(2))
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"))

    related_village: Mapped["Village | None"] = relationship(  # noqa: F821
        foreign_keys=[related_village_id]
    )
    source: Mapped["Source | None"] = relationship()  # noqa: F821
