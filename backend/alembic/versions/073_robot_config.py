"""073_robot_config

Revision ID: 5b4c7e8d9f01
Revises: f898322341a5
Create Date: 2026-10-30 14:30:00

群机器人配置表（飞书等平台的长连接机器人凭据存储）
"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes

# revision identifiers, used by Alembic.
revision = '5b4c7e8d9f01'
down_revision = 'f898322341a5'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'sys_robot_config',
        sa.Column('platform', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=False),
        sa.Column('app_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('app_secret_encrypted', sa.Text(), nullable=True),
        sa.Column('auto_start', sa.Boolean(), nullable=False),
        sa.Column('create_time', sa.BigInteger(), nullable=False),
        sa.Column('update_time', sa.BigInteger(), nullable=False),
        sa.Column('id', sa.BigInteger(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sys_robot_config_id'), 'sys_robot_config', ['id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_sys_robot_config_id'), table_name='sys_robot_config')
    op.drop_table('sys_robot_config')
