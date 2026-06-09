"""mensagem

Revision ID: 27b1482e9ad0
Revises: 
Create Date: 2026-04-18 15:44:47.274382

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '27b1482e9ad0'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table('usuarios'):
        op.create_table(
            'usuarios',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('email', sa.String(length=200), nullable=False),
            sa.Column('senha', sa.String(length=64), nullable=False),
            sa.Column('plano', sa.String(length=20), nullable=False, server_default='free'),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('email', name='uq_usuarios_email'),
        )
    else:
        existing_columns = {column['name'] for column in inspector.get_columns('usuarios')}
        with op.batch_alter_table('usuarios', schema=None) as batch_op:
            if 'plano' not in existing_columns:
                batch_op.add_column(sa.Column('plano', sa.String(length=20), nullable=False, server_default='free'))
            batch_op.alter_column('email',
                   existing_type=sa.VARCHAR(length=200),
                   nullable=False)
            batch_op.alter_column('senha',
                   existing_type=sa.VARCHAR(length=64),
                   nullable=False)

    inspector = sa.inspect(bind)
    if not inspector.has_table('tool_usages'):
        op.create_table(
            'tool_usages',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('session_id', sa.String(length=255), nullable=True),
            sa.Column('tool_name', sa.String(length=100), nullable=False),
            sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(['user_id'], ['usuarios.id']),
            sa.PrimaryKeyConstraint('id'),
        )

    if not inspector.has_table('daily_usages'):
        op.create_table(
            'daily_usages',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('user_id', sa.Integer(), nullable=True),
            sa.Column('session_id', sa.String(length=255), nullable=True),
            sa.Column('usage_date', sa.Date(), nullable=False),
            sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
            sa.ForeignKeyConstraint(['user_id'], ['usuarios.id']),
            sa.PrimaryKeyConstraint('id'),
        )


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if inspector.has_table('daily_usages'):
        op.drop_table('daily_usages')
    if inspector.has_table('tool_usages'):
        op.drop_table('tool_usages')
    if inspector.has_table('usuarios'):
        op.drop_table('usuarios')
