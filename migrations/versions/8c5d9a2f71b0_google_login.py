"""google login

Revision ID: 8c5d9a2f71b0
Revises: 27b1482e9ad0
Create Date: 2026-05-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '8c5d9a2f71b0'
down_revision = '27b1482e9ad0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.alter_column(
            'senha',
            existing_type=sa.String(length=64),
            nullable=True,
        )
        batch_op.add_column(sa.Column('nome', sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column('google_id', sa.String(length=255), nullable=True))
        batch_op.create_unique_constraint('uq_usuarios_google_id', ['google_id'])


def downgrade():
    with op.batch_alter_table('usuarios', schema=None) as batch_op:
        batch_op.drop_constraint('uq_usuarios_google_id', type_='unique')
        batch_op.drop_column('google_id')
        batch_op.drop_column('nome')
        batch_op.alter_column(
            'senha',
            existing_type=sa.String(length=64),
            nullable=False,
        )
