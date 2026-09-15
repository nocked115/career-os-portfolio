"""routines and learning step due dates

Revision ID: 0021_routines
Revises: 0020_checklist
Create Date: 2026-09-16 00:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0021_routines'
down_revision: Union[str, Sequence[str], None] = '0020_checklist'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'routines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('minutes', sa.Integer(), server_default='30', nullable=False),
        sa.Column('weekdays', sa.String(), server_default='0123456', nullable=False),
        sa.Column('target_count', sa.Integer(), nullable=True),
        sa.Column('unit_label', sa.String(), server_default='', nullable=False),
        sa.Column('learning_path_id', sa.Integer(), nullable=True),
        sa.Column('active', sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column('note', sa.Text(), server_default='', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['learning_path_id'], ['learning_paths.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_routines_id'), 'routines', ['id'], unique=False)

    op.create_table(
        'routine_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('routine_id', sa.Integer(), nullable=False),
        sa.Column('log_date', sa.Date(), nullable=False),
        sa.Column('count', sa.Integer(), nullable=True),
        sa.Column('minutes', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['routine_id'], ['routines.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('routine_id', 'log_date', name='uq_routine_log_day'),
    )
    op.create_index(op.f('ix_routine_logs_id'), 'routine_logs', ['id'], unique=False)
    op.create_index(op.f('ix_routine_logs_routine_id'), 'routine_logs', ['routine_id'], unique=False)
    op.create_index(op.f('ix_routine_logs_log_date'), 'routine_logs', ['log_date'], unique=False)

    # SQLite 는 이름 없는 제약을 배치 변경으로 만들지 못한다.
    with op.batch_alter_table('daily_plan_tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('routine_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_daily_plan_tasks_routine_id', 'routines', ['routine_id'], ['id'],
        )

    with op.batch_alter_table('learning_steps', schema=None) as batch_op:
        batch_op.add_column(sa.Column('due_date', sa.Date(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('learning_steps', schema=None) as batch_op:
        batch_op.drop_column('due_date')

    with op.batch_alter_table('daily_plan_tasks', schema=None) as batch_op:
        batch_op.drop_constraint('fk_daily_plan_tasks_routine_id', type_='foreignkey')
        batch_op.drop_column('routine_id')

    op.drop_index(op.f('ix_routine_logs_log_date'), table_name='routine_logs')
    op.drop_index(op.f('ix_routine_logs_routine_id'), table_name='routine_logs')
    op.drop_index(op.f('ix_routine_logs_id'), table_name='routine_logs')
    op.drop_table('routine_logs')
    op.drop_index(op.f('ix_routines_id'), table_name='routines')
    op.drop_table('routines')
