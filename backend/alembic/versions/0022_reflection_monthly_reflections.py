"""monthly reflections

Revision ID: 0022_reflection
Revises: 0021_routines
Create Date: 2026-09-16 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0022_reflection'
down_revision: Union[str, Sequence[str], None] = '0021_routines'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'monthly_reflections',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('year', sa.Integer(), nullable=False),
        sa.Column('month', sa.Integer(), nullable=False),
        sa.Column('rating', sa.Integer(), nullable=True),
        sa.Column('went_well', sa.Text(), server_default='', nullable=False),
        sa.Column('to_improve', sa.Text(), server_default='', nullable=False),
        sa.Column('next_focus', sa.Text(), server_default='', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('year', 'month', name='uq_reflection_month'),
    )
    op.create_index(op.f('ix_monthly_reflections_id'), 'monthly_reflections', ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_monthly_reflections_id'), table_name='monthly_reflections')
    op.drop_table('monthly_reflections')
