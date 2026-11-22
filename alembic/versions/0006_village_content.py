"""history, landmarks, heritage, economy and facilities

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

LANDMARKS = "'heritage_site','archaeological_site','traditional_building','spring','religious_site','viewpoint','other'"
HERITAGE = "'craft','food','agricultural_practice','custom','other'"
ECONOMIC = "'crop','agricultural_product','livestock','craft','industry','trade','other'"
FACILITIES = "'school','clinic','library','community_center','park','sports_facility','other'"


def _common():
    return [
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("village_id", sa.Integer(), sa.ForeignKey("villages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "historical_events", *_common(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("year", sa.Integer()),
        sa.Column("date_note", sa.String(100)),
        sa.CheckConstraint("year IS NOT NULL OR date_note IS NOT NULL", name="ck_events_when"),
    )
    op.create_index("ix_events_village_year", "historical_events", ["village_id", "year"])

    op.create_table(
        "landmarks", *_common(),
        sa.Column("name_ar", sa.String(150), nullable=False),
        sa.Column("name_en", sa.String(150)),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.CheckConstraint(f"category IN ({LANDMARKS})", name="ck_landmarks_category"),
        sa.CheckConstraint(
            "(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL)",
            name="ck_landmarks_coordinates_pair",
        ),
        sa.UniqueConstraint("village_id", "name_ar", name="uq_landmarks_village_name"),
    )
    op.create_index("ix_landmarks_village_category", "landmarks", ["village_id", "category"])

    op.create_table(
        "heritage_items", *_common(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("description", sa.Text()),
        sa.CheckConstraint(f"category IN ({HERITAGE})", name="ck_heritage_category"),
        sa.UniqueConstraint("village_id", "name", "category", name="uq_heritage_village_name_category"),
    )
    op.create_index("ix_heritage_village_category", "heritage_items", ["village_id", "category"])

    op.create_table(
        "economic_items", *_common(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(30), nullable=False),
        sa.Column("description", sa.Text()),
        sa.CheckConstraint(f"category IN ({ECONOMIC})", name="ck_economic_category"),
        sa.UniqueConstraint("village_id", "name", "category", name="uq_economic_village_name_category"),
    )
    op.create_index("ix_economic_village_category", "economic_items", ["village_id", "category"])

    op.create_table(
        "facilities", *_common(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("facility_type", sa.String(30), nullable=False),
        sa.Column("description", sa.Text()),
        sa.CheckConstraint(f"facility_type IN ({FACILITIES})", name="ck_facilities_type"),
        sa.UniqueConstraint("village_id", "name", "facility_type", name="uq_facilities_village_name_type"),
    )
    op.create_index("ix_facilities_village_type", "facilities", ["village_id", "facility_type"])


def downgrade() -> None:
    for table in ("facilities", "economic_items", "heritage_items", "landmarks", "historical_events"):
        op.drop_table(table)
