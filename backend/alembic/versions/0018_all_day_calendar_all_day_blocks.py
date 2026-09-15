"""calendar all-day blocks

Revision ID: 0018_all_day
Revises: 0017_links
Create Date: 2026-09-15 17:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0018_all_day'
down_revision: Union[str, Sequence[str], None] = '0017_links'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('calendar_blocks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('all_day', sa.Boolean(), server_default=sa.false(), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('calendar_blocks', schema=None) as batch_op:
        batch_op.drop_column('all_day')
