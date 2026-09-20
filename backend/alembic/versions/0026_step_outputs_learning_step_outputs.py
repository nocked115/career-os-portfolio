"""learning step outputs

Revision ID: 0026_step_outputs
Revises: 0025_routine_link
Create Date: 2026-09-16 14:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0026_step_outputs'
down_revision: Union[str, Sequence[str], None] = '0025_routine_link'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'learning_step_outputs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('learning_step_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('url', sa.String(), server_default='', nullable=False),
        sa.Column(
            'created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(['learning_step_id'], ['learning_steps.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_learning_step_outputs_id'),
        'learning_step_outputs',
        ['id'],
    )
    op.create_index(
        op.f('ix_learning_step_outputs_learning_step_id'),
        'learning_step_outputs',
        ['learning_step_id'],
    )

    with op.batch_alter_table('experiences', schema=None) as batch_op:
        batch_op.add_column(sa.Column('learning_step_id', sa.Integer(), nullable=True))
        batch_op.create_unique_constraint(
            'uq_experience_learning_step', ['learning_step_id']
        )
        batch_op.create_foreign_key(
            'fk_experience_learning_step',
            'learning_steps',
            ['learning_step_id'],
            ['id'],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('experiences', schema=None) as batch_op:
        batch_op.drop_constraint('fk_experience_learning_step', type_='foreignkey')
        batch_op.drop_constraint('uq_experience_learning_step', type_='unique')
        batch_op.drop_column('learning_step_id')

    op.drop_index(
        op.f('ix_learning_step_outputs_learning_step_id'),
        table_name='learning_step_outputs',
    )
    op.drop_index(
        op.f('ix_learning_step_outputs_id'), table_name='learning_step_outputs'
    )
    op.drop_table('learning_step_outputs')
