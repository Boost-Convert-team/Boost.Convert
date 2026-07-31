"""complete mercado pago payment records

Revision ID: b9e1c4a7d2f6
Revises: a6c4e8f1b2d7
Create Date: 2026-07-31
"""

from alembic import op
import sqlalchemy as sa


revision = "b9e1c4a7d2f6"
down_revision = "a6c4e8f1b2d7"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.add_column(
            sa.Column("external_reference", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(sa.Column("plan", sa.String(length=50), nullable=True))

    op.create_index(
        "ix_subscriptions_external_reference",
        "subscriptions",
        ["external_reference"],
    )
    op.create_index("ix_subscriptions_plan", "subscriptions", ["plan"])

    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(
            sa.Column("external_reference", sa.String(length=255), nullable=True)
        )
        batch_op.add_column(sa.Column("plan", sa.String(length=50), nullable=True))
        batch_op.add_column(
            sa.Column("idempotency_key", sa.String(length=64), nullable=True)
        )
        batch_op.add_column(
            sa.Column("payment_created_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("pix_ticket_url", sa.Text(), nullable=True))
        batch_op.create_unique_constraint(
            "uq_payments_provider_idempotency_key",
            ["provider", "idempotency_key"],
        )

    op.create_index("ix_payments_external_reference", "payments", ["external_reference"])
    op.create_index("ix_payments_plan", "payments", ["plan"])
    op.create_index("ix_payments_idempotency_key", "payments", ["idempotency_key"])

    backfill_mercado_pago_references()


def backfill_mercado_pago_references():
    for table_name in ("subscriptions", "payments"):
        table = sa.table(
            table_name,
            sa.column("user_id", sa.Integer()),
            sa.column("provider", sa.String()),
            sa.column("external_reference", sa.String()),
            sa.column("plan", sa.String()),
        )
        op.execute(
            table.update()
            .where(table.c.provider == "mercado_pago")
            .values(
                external_reference=(
                    sa.literal("boost:user:")
                    + sa.cast(table.c.user_id, sa.String())
                ),
                plan="BOOSTCONVERT_PRO",
            )
        )


def downgrade():
    op.drop_index("ix_payments_idempotency_key", table_name="payments")
    op.drop_index("ix_payments_plan", table_name="payments")
    op.drop_index("ix_payments_external_reference", table_name="payments")

    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_constraint("uq_payments_provider_idempotency_key", type_="unique")
        batch_op.drop_column("pix_ticket_url")
        batch_op.drop_column("payment_created_at")
        batch_op.drop_column("idempotency_key")
        batch_op.drop_column("plan")
        batch_op.drop_column("external_reference")

    op.drop_index("ix_subscriptions_plan", table_name="subscriptions")
    op.drop_index("ix_subscriptions_external_reference", table_name="subscriptions")

    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.drop_column("plan")
        batch_op.drop_column("external_reference")
