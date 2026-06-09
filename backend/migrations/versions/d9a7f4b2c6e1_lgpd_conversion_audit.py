"""lgpd conversion audit

Revision ID: d9a7f4b2c6e1
Revises: c8f1e2d9a4b0
Create Date: 2026-06-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d9a7f4b2c6e1"
down_revision = "c8f1e2d9a4b0"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "conversion_audit_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("session_id", sa.String(length=255), nullable=True),
        sa.Column("tool_name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["usuarios.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id"),
    )
    op.create_index(
        "ix_conversion_audit_logs_job_id",
        "conversion_audit_logs",
        ["job_id"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_conversion_audit_logs_job_id", table_name="conversion_audit_logs")
    op.drop_table("conversion_audit_logs")
