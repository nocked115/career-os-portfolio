"""plan focus skill

Revision ID: 0023_plan_focus
Revises: 0022_reflection
Create Date: 2026-09-16 09:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0023_plan_focus'
down_revision: Union[str, Sequence[str], None] = '0022_reflection'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('daily_plan_tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('plan_focus_skill', sa.String(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('daily_plan_tasks', schema=None) as batch_op:
        batch_op.drop_column('plan_focus_skill')
