"""allow leads saved from linkedin search without a score or ingestion run

Revision ID: 9d4e7f1a2b3c
Revises: 5a2b6c7d8e9f
Create Date: 2026-10-10 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9d4e7f1a2b3c"
down_revision: Union[str, None] = "5a2b6c7d8e9f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("leads") as batch:
        batch.alter_column("relevance_score", existing_type=sa.Integer(), nullable=True)
        batch.alter_column("ingestion_run_id", existing_type=sa.Integer(), nullable=True)


def downgrade() -> None:
    with op.batch_alter_table("leads") as batch:
        batch.alter_column("ingestion_run_id", existing_type=sa.Integer(), nullable=False)
        batch.alter_column("relevance_score", existing_type=sa.Integer(), nullable=False)
