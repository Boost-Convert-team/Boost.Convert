"""add attempt id real column

Revision ID: c4f6b6f42c1e
Revises: a8d4e6f2c1b9
"""

from uuid import NAMESPACE_URL, UUID, uuid5

import sqlalchemy as sa
from alembic import op

revision = "c4f6b6f42c1e"
down_revision = "a8d4e6f2c1b9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(
            sa.Column("attempt_id", sa.String(length=36), nullable=True)
        )

    payments = sa.table(
        "payments",
        sa.column("id", sa.Integer()),
        sa.column("provider", sa.String()),
        sa.column("attempt_id", sa.String()),
        sa.column("idempotency_key", sa.String()),
    )
    connection = op.get_bind()
    rows = connection.execute(
        sa.select(
            payments.c.id,
            payments.c.provider,
            payments.c.idempotency_key,
        )
    ).all()
    for payment_id, provider, idempotency_key in rows:
        try:
            attempt_id = str(UUID(str(idempotency_key or "").strip()))
        except (ValueError, AttributeError):
            attempt_id = str(
                uuid5(
                    NAMESPACE_URL,
                    f"boostconvert:payment:{provider}:{payment_id}",
                )
            )
        connection.execute(
            payments.update()
            .where(payments.c.id == payment_id)
            .values(attempt_id=attempt_id)
        )

    with op.batch_alter_table("payments") as batch_op:
        batch_op.alter_column(
            "attempt_id",
            existing_type=sa.String(length=36),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_payments_provider_attempt_id",
            ["provider", "attempt_id"],
        )
    op.create_index("ix_payments_attempt_id", "payments", ["attempt_id"])


def downgrade():
    op.drop_index("ix_payments_attempt_id", table_name="payments")
    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_constraint("uq_payments_provider_attempt_id", type_="unique")
        batch_op.drop_column("attempt_id")
