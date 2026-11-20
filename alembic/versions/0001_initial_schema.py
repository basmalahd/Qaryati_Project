"""initial schema: governorates, sources, villages, village_names, population_records

Revision ID: 0001
Revises:
Create Date: 2026-11-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def _timestamps():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "governorates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name_ar", sa.String(100), nullable=False, unique=True),
        sa.Column("name_en", sa.String(100), unique=True),
    )

    op.create_table(
        "sources",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False),
        sa.Column("author", sa.String(200)),
        sa.Column("url", sa.String(500)),
        sa.Column("publication_year", sa.Integer()),
        sa.Column("notes", sa.Text()),
        *_timestamps(),
    )

    op.create_table(
        "villages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("slug", sa.String(150), nullable=False, unique=True),
        sa.Column("name_ar", sa.String(150), nullable=False),
        sa.Column("name_en", sa.String(150)),
        sa.Column("name_origin", sa.Text()),
        sa.Column("historical_overview", sa.Text()),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("governorate_id", sa.Integer(), sa.ForeignKey("governorates.id", ondelete="RESTRICT"), nullable=False),
        *_timestamps(),
    )
    op.create_index("ix_villages_name_ar", "villages", ["name_ar"])
    op.create_index("ix_villages_name_en", "villages", ["name_en"])
    op.create_index("ix_villages_governorate_id", "villages", ["governorate_id"])

    op.create_table(
        "village_names",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("village_id", sa.Integer(), sa.ForeignKey("villages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("language", sa.String(10), nullable=False),
        sa.Column("name_type", sa.String(30), nullable=False),
        sa.Column("period_note", sa.String(200)),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="SET NULL")),
        *_timestamps(),
        sa.CheckConstraint(
            "name_type IN ('alternative_spelling','transliteration','former','historical')",
            name="ck_village_names_type",
        ),
    )
    op.create_index("ix_village_names_village_id", "village_names", ["village_id"])
    op.create_index("ix_village_names_name", "village_names", ["name"])

    op.create_table(
        "population_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("village_id", sa.Integer(), sa.ForeignKey("villages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("population", sa.Integer(), nullable=False),
        sa.Column("reference_year", sa.Integer(), nullable=False),
        sa.Column("source_id", sa.Integer(), sa.ForeignKey("sources.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("verification_status", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text()),
        *_timestamps(),
        sa.CheckConstraint("population >= 0", name="ck_population_non_negative"),
        sa.CheckConstraint("reference_year BETWEEN 1800 AND 2100", name="ck_population_year_range"),
        sa.CheckConstraint(
            "verification_status IN ('pending','verified','disputed')", name="ck_population_status"
        ),
        sa.UniqueConstraint("village_id", "reference_year", "source_id", name="uq_population_village_year_source"),
    )
    op.create_index("ix_population_village_year", "population_records", ["village_id", "reference_year"])


def downgrade() -> None:
    op.drop_table("population_records")
    op.drop_table("village_names")
    op.drop_table("villages")
    op.drop_table("sources")
    op.drop_table("governorates")
