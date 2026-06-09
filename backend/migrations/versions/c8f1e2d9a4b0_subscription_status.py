"""subscription status

Revision ID: c8f1e2d9a4b0
Revises: b4f2d8a7c901
Create Date: 2026-06-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "c8f1e2d9a4b0"
down_revision = "b4f2d8a7c901"
branch_labels = None
depends_on = None


def _has_column(table_name, column_name):
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return column_name in {column["name"] for column in inspector.get_columns(table_name)}


def upgrade():
    if not _has_column("usuarios", "status_assinatura"):
        with op.batch_alter_table("usuarios", schema=None) as batch_op:
            batch_op.add_column(
                sa.Column(
                    "status_assinatura",
                    sa.String(length=20),
                    nullable=False,
                    server_default="inactive",
                )
            )

        with op.batch_alter_table("usuarios", schema=None) as batch_op:
            batch_op.alter_column("status_assinatura", server_default=None)


def downgrade():
    if _has_column("usuarios", "status_assinatura"):
        with op.batch_alter_table("usuarios", schema=None) as batch_op:
            batch_op.drop_column("status_assinatura")
