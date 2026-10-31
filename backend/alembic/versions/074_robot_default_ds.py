"""074_robot_default_ds

Revision ID: a7f2e1c4b9d3
Revises: 5b4c7e8d9f01
Create Date: 2026-10-30 15:00:00

群机器人配置表新增默认数据源字段（default_datasource_id）
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a7f2e1c4b9d3'
down_revision = '5b4c7e8d9f01'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        'sys_robot_config',
        sa.Column('default_datasource_id', sa.BigInteger(), nullable=True),
    )


def downgrade():
    op.drop_column('sys_robot_config', 'default_datasource_id')
