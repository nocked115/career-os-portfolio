"""opportunity job fit filter

Revision ID: 0027_job_fit
Revises: 0026_step_outputs
Create Date: 2026-09-17 00:40:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0027_job_fit'
down_revision: Union[str, Sequence[str], None] = '0026_step_outputs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('opportunities', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('filtered_reason', sa.String(), server_default='', nullable=False)
        )
        batch_op.add_column(
            sa.Column('keep_anyway', sa.Boolean(), server_default='0', nullable=False)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('opportunities', schema=None) as batch_op:
        batch_op.drop_column('keep_anyway')
        batch_op.drop_column('filtered_reason')
