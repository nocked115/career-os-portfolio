"""collector runs

Revision ID: 0030_runs
Revises: 0029_dropped
Create Date: 2026-09-21 09:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0030_runs'
down_revision: Union[str, Sequence[str], None] = '0029_dropped'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'collector_runs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('error', sa.Text(), server_default='', nullable=False),
        sa.Column('fetched', sa.Integer(), nullable=False),
        sa.Column('created', sa.Integer(), nullable=False),
        sa.Column('ran_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', name='uq_collector_run_source'),
    )
    op.create_index(op.f('ix_collector_runs_id'), 'collector_runs', ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_collector_runs_id'), table_name='collector_runs')
    op.drop_table('collector_runs')
