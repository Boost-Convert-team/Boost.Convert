"""migrate recurring billing data model to Stripe

Revision ID: 9f2c7a4e1b8d
Revises: 481645ca061a
"""

import sqlalchemy as sa
from alembic import op

revision = "9f2c7a4e1b8d"
down_revision = "481645ca061a"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.add_column(sa.Column("stripe_customer_id", sa.String(length=120), nullable=True))
        batch_op.create_index("ix_usuarios_stripe_customer_id", ["stripe_customer_id"], unique=True)

    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.add_column(sa.Column("stripe_price_id", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("current_period_end", sa.DateTime(timezone=True), nullable=True))
        batch_op.add_column(
            sa.Column("cancel_at_period_end", sa.Boolean(), nullable=False, server_default=sa.false())
        )
        batch_op.create_index("ix_subscriptions_stripe_price_id", ["stripe_price_id"], unique=False)
        batch_op.create_index("ix_subscriptions_current_period_end", ["current_period_end"], unique=False)

    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_column("pix_ticket_url")
        batch_op.drop_column("pix_qr_code_base64")
        batch_op.drop_column("pix_qr_code")


def downgrade():
    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(sa.Column("pix_qr_code", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("pix_qr_code_base64", sa.Text(), nullable=True))
        batch_op.add_column(sa.Column("pix_ticket_url", sa.Text(), nullable=True))

    with op.batch_alter_table("subscriptions") as batch_op:
        batch_op.drop_index("ix_subscriptions_current_period_end")
        batch_op.drop_index("ix_subscriptions_stripe_price_id")
        batch_op.drop_column("cancel_at_period_end")
        batch_op.drop_column("current_period_end")
        batch_op.drop_column("stripe_price_id")

    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.drop_index("ix_usuarios_stripe_customer_id")
        batch_op.drop_column("stripe_customer_id")
