"""add linkedin search filters

Revision ID: a4d1e8c7f302
Revises: 3c8e1a7d9f20
Create Date: 2026-10-11 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a4d1e8c7f302"
down_revision: Union[str, None] = "3c8e1a7d9f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "linkedin_search_filters",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ignore_text", sa.String(length=300), nullable=False),
        sa.Column("removed_keys_json", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("linkedin_search_filters")
