"""add_admin_portal_tables

Revision ID: 00e46b805690
Revises: add_reporting_cols
Create Date: 2026-01-07 17:14:39.166047

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON


# revision identifiers, used by Alembic.
revision: str = '00e46b805690'
down_revision: Union[str, Sequence[str], None] = 'add_reporting_cols'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create admin portal tables: documents, admin_users, audit_logs."""

    # Documents table - tracks indexed documents for each practice
    op.create_table(
        'documents',
        sa.Column('doc_id', UUID(as_uuid=True), primary_key=True),
        sa.Column('client_id', UUID(as_uuid=True), sa.ForeignKey('clients.client_id'), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('source_type', sa.String(50), nullable=False),
        sa.Column('source_uri', sa.String(1000), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('chunk_count', sa.Integer, nullable=False, server_default='0'),
        sa.Column('error_message', sa.String, nullable=True),
        sa.Column('subagents_allowed', JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column('last_indexed_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_documents_client_id', 'documents', ['client_id'])
    op.create_index('ix_documents_status', 'documents', ['status'])

    # Admin Users table - admin portal authentication
    op.create_table(
        'admin_users',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('username', sa.String(100), nullable=False, unique=True),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=True),
        sa.Column('role', sa.String(50), nullable=False, server_default='admin'),
        sa.Column('is_active', sa.Boolean, nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('last_login_at', sa.DateTime, nullable=True),
    )
    op.create_index('ix_admin_users_username', 'admin_users', ['username'])

    # Audit Logs table - tracks all admin actions
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('actor', sa.String(100), nullable=False),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('practice_id', UUID(as_uuid=True), nullable=True),
        sa.Column('doc_id', UUID(as_uuid=True), nullable=True),
        sa.Column('result', sa.String(20), nullable=False, server_default='success'),
        sa.Column('details', JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )
    op.create_index('ix_audit_logs_created_at', 'audit_logs', ['created_at'])
    op.create_index('ix_audit_logs_actor', 'audit_logs', ['actor'])
    op.create_index('ix_audit_logs_action', 'audit_logs', ['action'])


def downgrade() -> None:
    """Drop admin portal tables."""
    op.drop_table('audit_logs')
    op.drop_table('admin_users')
    op.drop_table('documents')
