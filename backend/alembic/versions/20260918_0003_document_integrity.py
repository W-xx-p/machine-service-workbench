"""Enforce document identity at the database boundary.

Revision ID: 20260918_0003
Revises: 20260918_0002
Create Date: 2026-09-18
"""

from collections.abc import Sequence

from alembic import op


revision: str = "20260918_0003"
down_revision: str | None = "20260918_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_index("ix_documents_checksum")
        batch_op.create_unique_constraint("uq_documents_checksum", ["checksum"])
        batch_op.create_unique_constraint(
            "uq_documents_title_version", ["title", "version"]
        )


def downgrade() -> None:
    with op.batch_alter_table("documents") as batch_op:
        batch_op.drop_constraint("uq_documents_title_version", type_="unique")
        batch_op.drop_constraint("uq_documents_checksum", type_="unique")
        batch_op.create_index("ix_documents_checksum", ["checksum"], unique=False)
