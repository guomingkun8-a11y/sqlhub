"""Persist the answer and bounded query steps for web chat agents.

Revision ID: c36e84a2d5f1
Revises: a7f2e1c4b9d3
Create Date: 2026-10-30
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "c36e84a2d5f1"
down_revision = "a7f2e1c4b9d3"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chat_record", sa.Column("answer", sa.Text(), nullable=True))
    op.add_column(
        "chat_record", sa.Column("agent_steps", postgresql.JSONB(), nullable=True)
    )


def downgrade():
    op.drop_column("chat_record", "agent_steps")
    op.drop_column("chat_record", "answer")
