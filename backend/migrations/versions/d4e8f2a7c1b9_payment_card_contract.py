"""persist Mercado Pago card contract

Revision ID: d4e8f2a7c1b9
Revises: a8d4e6f2c1b9
Create Date: 2026-08-07
"""

import sqlalchemy as sa
from alembic import op

revision = "d4e8f2a7c1b9"
down_revision = "a8d4e6f2c1b9"
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("payments")}
    card_columns = {
        "provider_payment_method_id": sa.Column(
            "provider_payment_method_id", sa.String(length=50), nullable=True
        ),
        "payment_type_id": sa.Column(
            "payment_type_id", sa.String(length=50), nullable=True
        ),
        "installments": sa.Column("installments", sa.Integer(), nullable=True),
        "status_detail": sa.Column(
            "status_detail", sa.String(length=120), nullable=True
        ),
        "last_provider_sync_at": sa.Column(
            "last_provider_sync_at", sa.DateTime(timezone=True), nullable=True
        ),
    }
    missing_card_columns = [
        column for name, column in card_columns.items() if name not in existing_columns
    ]
    if missing_card_columns:
        with op.batch_alter_table("payments") as batch_op:
            for column in missing_card_columns:
                batch_op.add_column(column)

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

    inspector = sa.inspect(op.get_bind())
    existing_columns = {column["name"] for column in inspector.get_columns("payments")}
    missing_pix_columns = [
        name
        for name in ("pix_qr_code", "pix_qr_code_base64", "pix_ticket_url")
        if name not in existing_columns
    ]
    if missing_pix_columns:
        with op.batch_alter_table("payments") as batch_op:
            for name in missing_pix_columns:
                batch_op.add_column(sa.Column(name, sa.Text(), nullable=True))


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
