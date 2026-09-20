"""reflection dropped

Revision ID: 0029_dropped
Revises: 0028_dismissed
Create Date: 2026-09-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0029_dropped'
down_revision: Union[str, Sequence[str], None] = '0028_dismissed'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('monthly_reflections', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('dropped', sa.Text(), server_default='', nullable=False)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('monthly_reflections', schema=None) as batch_op:
        batch_op.drop_column('dropped')
