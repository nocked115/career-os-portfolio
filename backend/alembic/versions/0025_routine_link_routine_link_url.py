"""routine link url

Revision ID: 0025_routine_link
Revises: 0024_path_skills
Create Date: 2026-09-16 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0025_routine_link'
down_revision: Union[str, Sequence[str], None] = '0024_path_skills'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('routines', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('link_url', sa.String(), server_default='', nullable=False)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('routines', schema=None) as batch_op:
        batch_op.drop_column('link_url')
