"""Persist Feishu agent conversations and retire the old default datasource.

Revision ID: a0d8e9f17c42
Revises: e4b6a1c73d20
"""

import sqlalchemy as sa

from alembic import op

revision = "a0d8e9f17c42"
down_revision = "e4b6a1c73d20"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("chat", sa.Column("external_chat_id", sa.String(512), nullable=True))
    op.create_index(
        "ix_chat_external_chat_user",
        "chat",
        ["external_chat_id", "create_by"],
        unique=True,
    )
    op.drop_column("sys_robot_config", "default_datasource_id")


def downgrade():
    # The retired default datasource value cannot be reconstructed.
    op.add_column(
        "sys_robot_config",
        sa.Column("default_datasource_id", sa.BigInteger(), nullable=True),
    )
    op.drop_index("ix_chat_external_chat_user", table_name="chat")
    op.drop_column("chat", "external_chat_id")
