"""add pix checkout fields

Revision ID: a6c4e8f1b2d7
Revises: f3b6c8d2a1e4
Create Date: 2026-07-11
"""

from alembic import op
import sqlalchemy as sa


revision = "a6c4e8f1b2d7"
down_revision = "f3b6c8d2a1e4"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(sa.Column("pix_qr_code", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("pix_qr_code_base64", sa.Text(), nullable=True))


def downgrade():
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_column("pix_qr_code_base64")
        batch_op.drop_column("pix_qr_code")
        batch_op.drop_column("approved_at")
