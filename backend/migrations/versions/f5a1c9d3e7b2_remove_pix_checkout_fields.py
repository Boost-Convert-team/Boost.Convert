"""remove PIX checkout fields

Revision ID: f5a1c9d3e7b2
Revises: c4a8e2f1b7d9
Create Date: 2026-08-01 04:25:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "f5a1c9d3e7b2"
down_revision = "c4a8e2f1b7d9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.drop_column("pix_ticket_url")
        batch_op.drop_column("pix_qr_code_base64")
        batch_op.drop_column("pix_qr_code")


def downgrade():
    with op.batch_alter_table("payments", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pix_qr_code", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("pix_qr_code_base64", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("pix_ticket_url", sa.Text(), nullable=True))
