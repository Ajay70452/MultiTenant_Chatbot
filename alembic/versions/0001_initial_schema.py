"""initial_schema - create base tables

Revision ID: 0001_initial_schema
Revises:
Create Date: 2025-12-08

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '0001_initial_schema'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create base tables that existed before the access_token/practice_profiles migration."""

    # 1. Create clients table
    op.create_table(
        'clients',
        sa.Column('client_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('clinic_name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('lead_webhook_url', sa.String, nullable=True),
    )

    # 2. Create conversations table
    op.create_table(
        'conversations',
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.client_id'), nullable=False),
        sa.Column('current_stage', sa.String(50), nullable=False, server_default='GREETING'),
        sa.Column('conversation_state', sa.JSON, server_default='{}'),
        sa.Column('last_activity_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('is_finalized', sa.Boolean, server_default='false', nullable=False),
        sa.Column('finalized_at', sa.DateTime, nullable=True),
    )

    # 3. Create chat_logs table
    op.create_table(
        'chat_logs',
        sa.Column('log_id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.conversation_id'), nullable=False),
        sa.Column('sender_type', sa.String(10), nullable=False),
        sa.Column('message', sa.String, nullable=False),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('response_time_ms', sa.Integer, nullable=True),
    )

    # 4. Create webhook_attempts table
    op.create_table(
        'webhook_attempts',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.client_id'), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.conversation_id'), nullable=False),
        sa.Column('payload', sa.JSON, nullable=False),
        sa.Column('response_status_code', sa.Integer, nullable=True),
        sa.Column('response_text', sa.String, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # 5. Create webhook_failures table
    op.create_table(
        'webhook_failures',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.client_id'), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.conversation_id'), nullable=False),
        sa.Column('payload', sa.JSON, nullable=False),
        sa.Column('response_status_code', sa.Integer, nullable=True),
        sa.Column('response_text', sa.String, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    # 6. Create webhook_successes table
    op.create_table(
        'webhook_successes',
        sa.Column('id', sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column('client_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.client_id'), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('conversations.conversation_id'), nullable=False),
        sa.Column('payload', sa.JSON, nullable=False),
        sa.Column('response_status_code', sa.Integer, nullable=True),
        sa.Column('response_text', sa.String, nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )


def downgrade() -> None:
    """Drop all base tables."""
    op.drop_table('webhook_successes')
    op.drop_table('webhook_failures')
    op.drop_table('webhook_attempts')
    op.drop_table('chat_logs')
    op.drop_table('conversations')
    op.drop_table('clients')
