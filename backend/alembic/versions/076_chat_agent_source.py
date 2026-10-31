"""Persist the source record of a web chat analysis.

Revision ID: e4b6a1c73d20
Revises: c36e84a2d5f1
Create Date: 2026-10-30
"""

import sqlalchemy as sa

from alembic import op

revision = "e4b6a1c73d20"
down_revision = "c36e84a2d5f1"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chat_record", sa.Column("source_record_id", sa.BigInteger(), nullable=True))


def downgrade():
    op.drop_column("chat_record", "source_record_id")
