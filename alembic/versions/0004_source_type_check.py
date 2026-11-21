"""restrict sources.source_type to the known values

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-21
"""
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

TYPES = "'book','census','official','website','article','oral_history','other'"


def upgrade() -> None:
    # batch mode so it also works on SQLite (used by the test suite)
    with op.batch_alter_table("sources") as batch:
        batch.create_check_constraint("ck_sources_type", f"source_type IN ({TYPES})")


def downgrade() -> None:
    with op.batch_alter_table("sources") as batch:
        batch.drop_constraint("ck_sources_type", type_="check")
