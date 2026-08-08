"""add immutable payment attempt correlation

Revision ID: e2f7a9c4d1b6
Revises: c4a8e2f1b7d9
Create Date: 2026-07-31
"""

from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision = "e2f7a9c4d1b6"
down_revision = "c4a8e2f1b7d9"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("payments") as batch_op:
        batch_op.add_column(sa.Column("attempt_id", sa.String(length=36), nullable=True))
        batch_op.add_column(
            sa.Column("provider_payment_method_id", sa.String(length=50), nullable=True)
        )
        batch_op.add_column(sa.Column("payment_type", sa.String(length=50), nullable=True))
        batch_op.add_column(
            sa.Column("last_provider_sync_at", sa.DateTime(timezone=True), nullable=True)
        )

    backfill_attempt_ids()

    with op.batch_alter_table("payments") as batch_op:
        batch_op.alter_column("attempt_id", existing_type=sa.String(length=36), nullable=False)
        batch_op.create_unique_constraint(
            "uq_payments_provider_attempt_id",
            ["provider", "attempt_id"],
        )

    op.create_index("ix_payments_attempt_id", "payments", ["attempt_id"])
    op.create_index(
        "ix_payments_provider_payment_method_id",
        "payments",
        ["provider_payment_method_id"],
    )
    op.create_index("ix_payments_payment_type", "payments", ["payment_type"])
    op.create_index(
        "ix_payments_last_provider_sync_at",
        "payments",
        ["last_provider_sync_at"],
    )
    op.create_index(
        "uq_payments_provider_attempt_external_reference",
        "payments",
        ["provider", "external_reference"],
        unique=True,
        postgresql_where=sa.text("external_reference LIKE 'boost:payment:%'"),
        sqlite_where=sa.text("external_reference LIKE 'boost:payment:%'"),
    )


def backfill_attempt_ids():
    payments = sa.table(
        "payments",
        sa.column("id", sa.Integer()),
        sa.column("provider", sa.String()),
        sa.column("attempt_id", sa.String()),
    )
    connection = op.get_bind()
    rows = connection.execute(sa.select(payments.c.id, payments.c.provider)).all()
    for payment_id, provider in rows:
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


def downgrade():
    op.drop_index(
        "uq_payments_provider_attempt_external_reference",
        table_name="payments",
    )
    op.drop_index("ix_payments_last_provider_sync_at", table_name="payments")
    op.drop_index("ix_payments_payment_type", table_name="payments")
    op.drop_index("ix_payments_provider_payment_method_id", table_name="payments")
    op.drop_index("ix_payments_attempt_id", table_name="payments")

    with op.batch_alter_table("payments") as batch_op:
        batch_op.drop_constraint("uq_payments_provider_attempt_id", type_="unique")
        batch_op.drop_column("last_provider_sync_at")
        batch_op.drop_column("payment_type")
        batch_op.drop_column("provider_payment_method_id")
        batch_op.drop_column("attempt_id")
