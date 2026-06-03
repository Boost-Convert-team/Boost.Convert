"""conversion jobs

Revision ID: 2f4a0c8d91e7
Revises: 8c5d9a2f71b0
Create Date: 2026-05-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = '2f4a0c8d91e7'
down_revision = '8c5d9a2f71b0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'conversion_jobs',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.String(length=255), nullable=True),
        sa.Column('tool_name', sa.String(length=100), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('original_filename', sa.String(length=255), nullable=False),
        sa.Column('output_filename', sa.String(length=255), nullable=False),
        sa.Column('input_path', sa.String(length=500), nullable=False),
        sa.Column('output_path', sa.String(length=500), nullable=False),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('finished_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['usuarios.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('conversion_jobs')
