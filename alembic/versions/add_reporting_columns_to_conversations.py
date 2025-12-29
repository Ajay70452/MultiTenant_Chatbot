"""Add reporting columns to conversations table

Revision ID: add_reporting_cols
Revises: 8a1d0d11840a
Create Date: 2025-12-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_reporting_cols'
down_revision: Union[str, Sequence[str], None] = '8a1d0d11840a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add reporting columns to conversations table for AI Chat Dashboard."""

    # Add lead_captured column
    op.add_column(
        'conversations',
        sa.Column('lead_captured', sa.Boolean(), nullable=False, server_default='false')
    )

    # Add delivery_status column
    op.add_column(
        'conversations',
        sa.Column('delivery_status', sa.String(50), nullable=True)
    )

    # Add topic_tag column
    op.add_column(
        'conversations',
        sa.Column('topic_tag', sa.String(100), nullable=True)
    )

    # Add is_after_hours column
    op.add_column(
        'conversations',
        sa.Column('is_after_hours', sa.Boolean(), nullable=False, server_default='false')
    )


def downgrade() -> None:
    """Remove reporting columns from conversations table."""
    op.drop_column('conversations', 'is_after_hours')
    op.drop_column('conversations', 'topic_tag')
    op.drop_column('conversations', 'delivery_status')
    op.drop_column('conversations', 'lead_captured')
