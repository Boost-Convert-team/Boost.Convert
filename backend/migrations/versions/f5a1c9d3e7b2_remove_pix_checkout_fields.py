"""preserve PIX checkout fields

Revision ID: f5a1c9d3e7b2
Revises: e2f7a9c4d1b6
Create Date: 2026-08-01 04:25:00.000000
"""

revision = "f5a1c9d3e7b2"
down_revision = "e2f7a9c4d1b6"
branch_labels = None
depends_on = None


def upgrade():
    # Kept as a no-op so databases upgrading from c4a8e2f1b7d9 do not lose
    # active PIX checkout data. The next billing revision repairs databases
    # where the original destructive version was already applied.
    pass


def downgrade():
    pass
