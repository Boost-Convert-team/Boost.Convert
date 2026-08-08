"""persist Mercado Pago card contract

Revision ID: d4e8f2a7c1b9
Revises: a8d4e6f2c1b9
Create Date: 2026-08-07
"""

from alembic import op
import sqlalchemy as sa


revision = "d4e8f2a7c1b9"
down_revision = "a8d4e6f2c1b9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(
            sa.Column("provider_payment_method_id", sa.String(length=50), nullable=True)
        )
        batch_op.add_column(
            sa.Column("payment_type_id", sa.String(length=50), nullable=True)
        )
        batch_op.add_column(sa.Column("installments", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("status_detail", sa.String(length=120), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_provider_sync_at", sa.DateTime(timezone=True), nullable=True)
        )

    op.create_index(
        "ix_payments_provider_payment_method_id",
        "payments",
        ["provider_payment_method_id"],
    )
    op.create_index("ix_payments_payment_type_id", "payments", ["payment_type_id"])
    op.create_index(
        "ix_payments_last_provider_sync_at",
        "payments",
        ["last_provider_sync_at"],
    )

    payments = sa.table(
        "payments",
        sa.column("payment_method", sa.String()),
        sa.column("payment_type_id", sa.String()),
    )
    op.execute(
        payments.update()
        .where(payments.c.payment_method.in_(["credit_card", "debit_card"]))
        .values(payment_type_id=payments.c.payment_method)
    )


def downgrade():
    op.drop_index("ix_payments_last_provider_sync_at", table_name="payments")
    op.drop_index("ix_payments_payment_type_id", table_name="payments")
    op.drop_index("ix_payments_provider_payment_method_id", table_name="payments")

    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_column("last_provider_sync_at")
        batch_op.drop_column("status_detail")
        batch_op.drop_column("installments")
        batch_op.drop_column("payment_type_id")
        batch_op.drop_column("provider_payment_method_id")
