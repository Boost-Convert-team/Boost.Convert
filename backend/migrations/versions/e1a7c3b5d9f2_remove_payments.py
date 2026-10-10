"""remove payments: PRO becomes a plan stored on the account

Revision ID: e1a7c3b5d9f2
Revises: d2f8a4c6e9b1
Create Date: 2026-10-09

Mercado Pago was removed from the product. Users whose paid access is still
valid keep the PRO plan; everyone else becomes Free. Then the billing tables,
the subscription status column and the unused tool_usages table are dropped.

Irreversible: back up the billing tables before running it if their history
is still needed.
"""

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "e1a7c3b5d9f2"
down_revision = "d2f8a4c6e9b1"
branch_labels = None
depends_on = None

DROPPED_TABLES = (
    "payment_webhook_events",
    "payment_plan_mappings",
    "payments",
    "subscriptions",
    "tool_usages",
)


def upgrade():
    # Same rule the removed billing code used: an active subscription paid
    # through today, an approved one-time payment not yet expired, or a PRO
    # flag set by hand on an account that never had billing records.
    op.get_bind().execute(
        sa.text(
            """
            UPDATE usuarios SET plano = CASE WHEN (
                EXISTS (
                    SELECT 1 FROM subscriptions s
                    WHERE s.user_id = usuarios.id
                      AND s.status = 'active'
                      AND s.paid_through_at > :now
                )
                OR EXISTS (
                    SELECT 1 FROM payments p
                    WHERE p.user_id = usuarios.id
                      AND p.payment_method = 'credit_card'
                      AND p.status = 'approved'
                      AND p.premium_expires_at > :now
                )
                OR (
                    usuarios.plano = 'pro'
                    AND usuarios.status_assinatura = 'active'
                    AND NOT EXISTS (SELECT 1 FROM subscriptions s2 WHERE s2.user_id = usuarios.id)
                    AND NOT EXISTS (SELECT 1 FROM payments p2 WHERE p2.user_id = usuarios.id)
                )
            ) THEN 'pro' ELSE 'free' END
            """
        ),
        {"now": datetime.now(timezone.utc)},
    )

    with op.batch_alter_table("usuarios") as batch_op:
        batch_op.drop_column("status_assinatura")

    for table_name in DROPPED_TABLES:
        op.drop_table(table_name)


def downgrade():
    raise RuntimeError(
        "e1a7c3b5d9f2 deleted the billing tables and their rows; restore them from a backup."
    )
