"""recurring Mercado Pago subscriptions

Revision ID: b7d3e9f1a2c4
Revises: 6b7e8f901a2c
Create Date: 2026-08-17
"""

import sqlalchemy as sa
from alembic import op

revision = "b7d3e9f1a2c4"
down_revision = "6b7e8f901a2c"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "payment_plan_mappings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("plan", sa.String(length=50), nullable=False),
        sa.Column("provider_plan_id", sa.String(length=120), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider", "plan", name="uq_payment_plan_mappings_provider_plan"
        ),
        sa.UniqueConstraint(
            "provider",
            "provider_plan_id",
            name="uq_payment_plan_mappings_provider_plan_id",
        ),
    )
    op.create_index(
        "ix_payment_plan_mappings_provider", "payment_plan_mappings", ["provider"]
    )
    op.create_index("ix_payment_plan_mappings_plan", "payment_plan_mappings", ["plan"])
    op.create_index(
        "ix_payment_plan_mappings_provider_plan_id",
        "payment_plan_mappings",
        ["provider_plan_id"],
    )

    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.add_column(sa.Column("provider_plan_id", sa.String(120), nullable=True))
        batch_op.add_column(
            sa.Column("checkout_idempotency_key", sa.String(64), nullable=True)
        )
        batch_op.add_column(sa.Column("checkout_url", sa.Text(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_subscriptions_provider_checkout_idempotency",
            ["provider", "checkout_idempotency_key"],
        )
    op.create_index(
        "ix_subscriptions_provider_plan_id", "subscriptions", ["provider_plan_id"]
    )
    op.create_index(
        "ix_subscriptions_checkout_idempotency_key",
        "subscriptions",
        ["checkout_idempotency_key"],
    )

    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(sa.Column("provider_invoice_id", sa.String(120), nullable=True))
        batch_op.create_unique_constraint(
            "uq_payments_provider_invoice_id", ["provider", "provider_invoice_id"]
        )
    op.create_index(
        "ix_payments_provider_invoice_id", "payments", ["provider_invoice_id"]
    )


def downgrade():
    op.drop_index("ix_payments_provider_invoice_id", table_name="payments")
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_constraint("uq_payments_provider_invoice_id", type_="unique")
        batch_op.drop_column("provider_invoice_id")

    op.drop_index(
        "ix_subscriptions_checkout_idempotency_key", table_name="subscriptions"
    )
    op.drop_index("ix_subscriptions_provider_plan_id", table_name="subscriptions")
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.drop_constraint(
            "uq_subscriptions_provider_checkout_idempotency", type_="unique"
        )
        batch_op.drop_column("checkout_url")
        batch_op.drop_column("checkout_idempotency_key")
        batch_op.drop_column("provider_plan_id")

    op.drop_index(
        "ix_payment_plan_mappings_provider_plan_id",
        table_name="payment_plan_mappings",
    )
    op.drop_index("ix_payment_plan_mappings_plan", table_name="payment_plan_mappings")
    op.drop_index(
        "ix_payment_plan_mappings_provider", table_name="payment_plan_mappings"
    )
    op.drop_table("payment_plan_mappings")
