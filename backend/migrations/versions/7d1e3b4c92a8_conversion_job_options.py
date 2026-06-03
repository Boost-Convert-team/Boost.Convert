"""conversion job options

Revision ID: 7d1e3b4c92a8
Revises: 2f4a0c8d91e7
Create Date: 2026-05-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '7d1e3b4c92a8'
down_revision = '2f4a0c8d91e7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('conversion_jobs', schema=None) as batch_op:
        batch_op.add_column(sa.Column('options', sa.JSON(), nullable=False, server_default='{}'))

    with op.batch_alter_table('conversion_jobs', schema=None) as batch_op:
        batch_op.alter_column('options', server_default=None)


def downgrade():
    with op.batch_alter_table('conversion_jobs', schema=None) as batch_op:
        batch_op.drop_column('options')
