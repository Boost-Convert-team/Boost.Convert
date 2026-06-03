"""usage window started at

Revision ID: a1b2c3d4e5f6
Revises: 7d1e3b4c92a8
Create Date: 2026-05-23 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a1b2c3d4e5f6'
down_revision = '7d1e3b4c92a8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('daily_usages', schema=None) as batch_op:
        batch_op.add_column(sa.Column('window_started_at', sa.DateTime(timezone=True), nullable=True))

    op.create_index(
        'ix_daily_usages_user_id',
        'daily_usages',
        ['user_id'],
        unique=False,
    )
    op.create_index(
        'ix_daily_usages_session_id',
        'daily_usages',
        ['session_id'],
        unique=False,
    )


def downgrade():
    op.drop_index('ix_daily_usages_session_id', table_name='daily_usages')
    op.drop_index('ix_daily_usages_user_id', table_name='daily_usages')

    with op.batch_alter_table('daily_usages', schema=None) as batch_op:
        batch_op.drop_column('window_started_at')
