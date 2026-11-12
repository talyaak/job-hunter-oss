"""add rag filter pipeline

Revision ID: 5a2b6c7d8e9f
Revises: cb7f8b49c51b
Create Date: 2026-06-13 08:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "5a2b6c7d8e9f"
down_revision: Union[str, None] = "cb7f8b49c51b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "job_embeddings",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("job_url", sa.String(length=1000), nullable=False),
        sa.Column("job_title", sa.String(length=500), nullable=True),
        sa.Column("company", sa.String(length=255), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("embedding_json", sa.Text(), nullable=False),
        sa.Column("source_stage", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_job_embeddings_content_hash"), "job_embeddings", ["content_hash"], unique=False)
    op.create_index(op.f("ix_job_embeddings_job_url"), "job_embeddings", ["job_url"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_embeddings_job_url"), table_name="job_embeddings")
    op.drop_index(op.f("ix_job_embeddings_content_hash"), table_name="job_embeddings")
    op.drop_table("job_embeddings")
