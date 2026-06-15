"""Add audit_log table

Revision ID: a1f4c2d9b7e3
Revises: fe56fa70289e
Create Date: 2026-06-16 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision = 'a1f4c2d9b7e3'
down_revision = 'fe56fa70289e'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'audit_log',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('actor_user_id', sa.Uuid(), nullable=True),
        sa.Column('action', sqlmodel.sql.sqltypes.AutoString(length=100), nullable=False),
        sa.Column('target_type', sqlmodel.sql.sqltypes.AutoString(length=50), nullable=False),
        sa.Column('target_id', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True),
        sa.Column('summary', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['actor_user_id'], ['user.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_audit_log_actor_user_id'), 'audit_log', ['actor_user_id'], unique=False)
    op.create_index(op.f('ix_audit_log_action'), 'audit_log', ['action'], unique=False)
    op.create_index(op.f('ix_audit_log_target_type'), 'audit_log', ['target_type'], unique=False)
    op.create_index(op.f('ix_audit_log_target_id'), 'audit_log', ['target_id'], unique=False)
    op.create_index(op.f('ix_audit_log_created_at'), 'audit_log', ['created_at'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_audit_log_created_at'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_target_id'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_target_type'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_action'), table_name='audit_log')
    op.drop_index(op.f('ix_audit_log_actor_user_id'), table_name='audit_log')
    op.drop_table('audit_log')
