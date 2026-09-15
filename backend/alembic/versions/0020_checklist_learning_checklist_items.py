"""learning checklist items

Revision ID: 0020_checklist
Revises: 0019_certificates
Create Date: 2026-09-15 23:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0020_checklist'
down_revision: Union[str, Sequence[str], None] = '0019_certificates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'learning_checklist_items',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('learning_step_id', sa.Integer(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('section', sa.String(), server_default='', nullable=False),
        sa.Column('kind', sa.String(), server_default='task', nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('url', sa.String(), server_default='', nullable=False),
        sa.Column('done', sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column('done_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['learning_step_id'], ['learning_steps.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_learning_checklist_items_id'), 'learning_checklist_items', ['id'], unique=False)
    op.create_index(op.f('ix_learning_checklist_items_learning_step_id'), 'learning_checklist_items', ['learning_step_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_learning_checklist_items_learning_step_id'), table_name='learning_checklist_items')
    op.drop_index(op.f('ix_learning_checklist_items_id'), table_name='learning_checklist_items')
    op.drop_table('learning_checklist_items')
