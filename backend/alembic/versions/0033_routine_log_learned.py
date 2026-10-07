"""routine log: 그날 몰랐던 것

Revision ID: 0033_log_learned
Revises: 0032_exp_depth
Create Date: 2026-09-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0033_log_learned'
down_revision: Union[str, Sequence[str], None] = '0032_exp_depth'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('routine_logs', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('learned', sa.Text(), server_default='', nullable=False)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('routine_logs', schema=None) as batch_op:
        batch_op.drop_column('learned')
