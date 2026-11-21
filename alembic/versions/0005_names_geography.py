"""village elevation/area, unique alternative names, nearby_places

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

RELATIONS = "'borders','nearby','nearest_city'"
DIRECTIONS = "'N','NE','E','SE','S','SW','W','NW'"


def upgrade() -> None:
    with op.batch_alter_table("villages") as batch:
        batch.add_column(sa.Column("elevation_m", sa.Float()))
        batch.add_column(sa.Column("area_km2", sa.Float()))
        batch.create_check_constraint(
            "ck_villages_elevation_range",
            "elevation_m IS NULL OR (elevation_m >= -500 AND elevation_m <= 3000)",
        )
        batch.create_check_constraint("ck_villages_area_positive", "area_km2 IS NULL OR area_km2 > 0")

    with op.batch_alter_table("village_names") as batch:
        batch.create_unique_constraint("uq_village_names_unique", ["village_id", "name", "name_type"])

    op.create_table(
        "nearby_places",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("village_id", sa.Integer(), sa.ForeignKey("villages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("related_village_id", sa.Integer(), sa.ForeignKey("villages.id", ondelete="CASCADE")),
        sa.Column("place_name", sa.String(150)),
        sa.Column("relation_type", sa.String(20), nullable=False),
        sa.Column("distance_km", sa.Float()),
        sa.Column("direction", sa.String(2)),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(f"relation_type IN ({RELATIONS})", name="ck_nearby_relation_type"),
        sa.CheckConstraint(f"direction IS NULL OR direction IN ({DIRECTIONS})", name="ck_nearby_direction"),
        sa.CheckConstraint(
            "(related_village_id IS NOT NULL AND place_name IS NULL) OR "
            "(related_village_id IS NULL AND place_name IS NOT NULL)",
            name="ck_nearby_exactly_one_target",
        ),
        sa.CheckConstraint("related_village_id IS NULL OR related_village_id <> village_id", name="ck_nearby_not_self"),
        sa.CheckConstraint("distance_km IS NULL OR distance_km >= 0", name="ck_nearby_distance"),
    )
    op.create_index("ix_nearby_village_id", "nearby_places", ["village_id"])
    op.create_index(
        "uq_nearby_village_rel", "nearby_places", ["village_id", "related_village_id", "relation_type"],
        unique=True,
        postgresql_where=sa.text("related_village_id IS NOT NULL"),
        sqlite_where=sa.text("related_village_id IS NOT NULL"),
    )
    op.create_index(
        "uq_nearby_place_rel", "nearby_places", ["village_id", "place_name", "relation_type"],
        unique=True,
        postgresql_where=sa.text("place_name IS NOT NULL"),
        sqlite_where=sa.text("place_name IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_table("nearby_places")
    with op.batch_alter_table("village_names") as batch:
        batch.drop_constraint("uq_village_names_unique", type_="unique")
    with op.batch_alter_table("villages") as batch:
        batch.drop_constraint("ck_villages_area_positive", type_="check")
        batch.drop_constraint("ck_villages_elevation_range", type_="check")
        batch.drop_column("area_km2")
        batch.drop_column("elevation_m")
