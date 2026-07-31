"""track paid recurring subscription entitlement

Revision ID: c4a8e2f1b7d9
Revises: b9e1c4a7d2f6
Create Date: 2026-07-31
"""

from alembic import op
import sqlalchemy as sa


revision = "c4a8e2f1b7d9"
down_revision = "b9e1c4a7d2f6"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.add_column(
            sa.Column("paid_through_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("latest_payment_status", sa.String(length=50), nullable=True)
        )

    op.create_index(
        "ix_subscriptions_paid_through_at",
        "subscriptions",
        ["paid_through_at"],
    )
    op.create_index(
        "ix_subscriptions_latest_payment_status",
        "subscriptions",
        ["latest_payment_status"],
    )
    backfill_existing_paid_subscriptions()


def backfill_existing_paid_subscriptions():
    subscriptions = sa.table(
        "subscriptions",
        sa.column("user_id", sa.Integer()),
        sa.column("provider", sa.String()),
        sa.column("provider_subscription_id", sa.String()),
        sa.column("paid_through_at", sa.DateTime(timezone=True)),
        sa.column("latest_payment_status", sa.String()),
    )
    payments = sa.table(
        "payments",
        sa.column("user_id", sa.Integer()),
        sa.column("provider", sa.String()),
        sa.column("provider_subscription_id", sa.String()),
        sa.column("status", sa.String()),
        sa.column("premium_expires_at", sa.DateTime(timezone=True)),
    )
    approved_expiration = (
        sa.select(sa.func.max(payments.c.premium_expires_at))
        .where(
            payments.c.user_id == subscriptions.c.user_id,
            payments.c.provider == subscriptions.c.provider,
            payments.c.provider_subscription_id
            == subscriptions.c.provider_subscription_id,
            payments.c.status == "approved",
            payments.c.premium_expires_at.is_not(None),
        )
        .correlate(subscriptions)
        .scalar_subquery()
    )
    op.execute(
        subscriptions.update()
        .where(approved_expiration.is_not(None))
        .values(
            paid_through_at=approved_expiration,
            latest_payment_status="approved",
        )
    )


def downgrade():
    op.drop_index("ix_subscriptions_latest_payment_status", table_name="subscriptions")
    op.drop_index("ix_subscriptions_paid_through_at", table_name="subscriptions")

    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.drop_column("latest_payment_status")
        batch_op.drop_column("paid_through_at")
