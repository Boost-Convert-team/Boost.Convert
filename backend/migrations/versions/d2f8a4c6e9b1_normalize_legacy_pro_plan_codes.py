"""normalize legacy PRO plan codes

Revision ID: d2f8a4c6e9b1
Revises: b7d3e9f1a2c4
Create Date: 2026-08-17
"""

import sqlalchemy as sa
from alembic import op

revision = "d2f8a4c6e9b1"
down_revision = "b7d3e9f1a2c4"
branch_labels = None
depends_on = None


def upgrade():
    connection = op.get_bind()
    for table_name in ("subscriptions", "payments"):
        table = sa.table(
            table_name,
            sa.column("plan", sa.String()),
        )
        connection.execute(
            table.update().where(table.c.plan == "BOOSTCONVERT_PRO").values(plan="PRO")
        )


def downgrade():
    # "PRO" is also the canonical value for new rows, so reverting it would
    # corrupt records created after this migration.
    pass
