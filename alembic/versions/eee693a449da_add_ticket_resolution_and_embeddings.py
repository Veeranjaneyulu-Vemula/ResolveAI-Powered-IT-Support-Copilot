"""add ticket resolution and embeddings

Revision ID: eee693a449da
Revises: 92a1515994cb
Create Date: 2026-08-15 11:57:36.920927

"""
from typing import Sequence, Union

from alembic import op
from pgvector.sqlalchemy import Vector
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'eee693a449da'
down_revision: Union[str, Sequence[str], None] = '92a1515994cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column('tickets', sa.Column('resolution', sa.Text(), nullable=True))
    op.add_column(
        'tickets',
        sa.Column('embedding', Vector(1536), nullable=True),
    )
    op.add_column('tickets', sa.Column('embedding_model', sa.String(length=100), nullable=True))
    op.add_column('tickets', sa.Column('embedding_updated_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('tickets', 'embedding_updated_at')
    op.drop_column('tickets', 'embedding_model')
    op.drop_column('tickets', 'embedding')
    op.drop_column('tickets', 'resolution')
    op.execute("DROP EXTENSION IF EXISTS vector")
