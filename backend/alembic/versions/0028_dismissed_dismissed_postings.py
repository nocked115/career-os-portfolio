"""dismissed postings

Revision ID: 0028_dismissed
Revises: 0027_job_fit
Create Date: 2026-09-17 01:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0028_dismissed'
down_revision: Union[str, Sequence[str], None] = '0027_job_fit'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'dismissed_postings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('source_external_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'source_external_id', name='uq_dismissed_posting'),
    )
    op.create_index(op.f('ix_dismissed_postings_id'), 'dismissed_postings', ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_dismissed_postings_id'), table_name='dismissed_postings')
    op.drop_table('dismissed_postings')
