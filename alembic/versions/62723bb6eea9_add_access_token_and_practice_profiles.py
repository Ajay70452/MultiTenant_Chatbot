"""add_access_token_and_practice_profiles

Revision ID: 62723bb6eea9
Revises: 
Create Date: 2025-12-08 07:01:08.279947

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '62723bb6eea9'
down_revision: Union[str, Sequence[str], None] = '0001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: Add access_token to clients and create practice_profiles table."""

    # 1. Add access_token column to clients table
    op.add_column(
        'clients',
        sa.Column('access_token', sa.String(64), nullable=True)
    )
    op.create_index('ix_clients_access_token', 'clients', ['access_token'], unique=True)

    # 2. Create practice_profiles table
    op.create_table(
        'practice_profiles',
        sa.Column('practice_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('clients.client_id'), primary_key=True),
        sa.Column('profile_json', postgresql.JSONB, nullable=False, server_default='{}'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now(), onupdate=sa.func.now())
    )


def downgrade() -> None:
    """Downgrade schema: Remove access_token from clients and drop practice_profiles table."""

    # 1. Drop practice_profiles table
    op.drop_table('practice_profiles')

    # 2. Remove access_token column from clients table
    op.drop_index('ix_clients_access_token', table_name='clients')
    op.drop_column('clients', 'access_token')
