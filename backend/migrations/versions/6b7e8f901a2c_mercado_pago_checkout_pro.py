"""migrate billing to Mercado Pago Checkout Pro

Revision ID: 6b7e8f901a2c
Revises: 9f2c7a4e1b8d
"""

import sqlalchemy as sa
from alembic import op

revision = "6b7e8f901a2c"
down_revision = "9f2c7a4e1b8d"
branch_labels = None
depends_on = None


def upgrade():
    drop_columns(
        "usuarios",
        ["stripe_customer_id"],
        ["ix_usuarios_stripe_customer_id"],
    )
    drop_columns(
        "subscriptions",
        ["stripe_price_id", "current_period_end", "cancel_at_period_end"],
        ["ix_subscriptions_stripe_price_id", "ix_subscriptions_current_period_end"],
    )
    drop_columns(
        "payments",
        [
            "provider_subscription_id",
            "provider_payment_method_id",
            "payment_type_id",
            "installments",
            "pix_qr_code",
            "pix_qr_code_base64",
            "pix_ticket_url",
        ],
        [
            "ix_payments_provider_subscription_id",
            "ix_payments_provider_payment_method_id",
            "ix_payments_payment_type_id",
        ],
    )
    add_payment_checkout_columns()


def downgrade():
    drop_columns(
        "payments",
        ["provider_preference_id", "checkout_url", "checkout_expires_at"],
        [
            "ix_payments_provider_preference_id",
            "ix_payments_checkout_expires_at",
        ],
    )


def add_payment_checkout_columns():
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("payments")}
    additions = []
    if "provider_preference_id" not in columns:
        additions.append(
            sa.Column("provider_preference_id", sa.String(length=120), nullable=True)
        )
    if "checkout_url" not in columns:
        additions.append(sa.Column("checkout_url", sa.Text(), nullable=True))
    if "checkout_expires_at" not in columns:
        additions.append(
            sa.Column("checkout_expires_at", sa.DateTime(timezone=True), nullable=True)
        )
    if additions:
        with op.batch_alter_table("payments") as batch_op:
            for column in additions:
                batch_op.add_column(column)

    inspector = sa.inspect(op.get_bind())
    indexes = {index["name"] for index in inspector.get_indexes("payments")}
    if "ix_payments_provider_preference_id" not in indexes:
        op.create_index(
            "ix_payments_provider_preference_id",
            "payments",
            ["provider_preference_id"],
        )
    if "ix_payments_checkout_expires_at" not in indexes:
        op.create_index(
            "ix_payments_checkout_expires_at",
            "payments",
            ["checkout_expires_at"],
        )


def drop_columns(table_name, column_names, index_names):
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return
    existing_columns = {
        column["name"] for column in inspector.get_columns(table_name)
    }
    existing_indexes = {
        index["name"] for index in inspector.get_indexes(table_name)
    }
    indexes_to_drop = [name for name in index_names if name in existing_indexes]
    columns_to_drop = [name for name in column_names if name in existing_columns]
    if not indexes_to_drop and not columns_to_drop:
        return
    with op.batch_alter_table(table_name) as batch_op:
        for index_name in indexes_to_drop:
            batch_op.drop_index(index_name)
        for column_name in columns_to_drop:
            batch_op.drop_column(column_name)
