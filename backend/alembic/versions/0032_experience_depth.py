"""experience depth fields

Revision ID: 0032_exp_depth
Revises: 0031_purpose
Create Date: 2026-09-22 01:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0032_exp_depth'
down_revision: Union[str, Sequence[str], None] = '0031_purpose'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


COLUMNS = (
    "stakeholders", "contribution", "obstacles",
    "learned", "reusable", "target_roles", "questions",
)


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('experiences', schema=None) as batch_op:
        for name in COLUMNS:
            batch_op.add_column(
                sa.Column(name, sa.Text(), server_default='', nullable=False)
            )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('experiences', schema=None) as batch_op:
        for name in reversed(COLUMNS):
            batch_op.drop_column(name)
