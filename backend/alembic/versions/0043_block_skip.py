"""달력: 매주 반복에서 하루만 빼기

Revision ID: 0043_block_skip
Revises: 0042_step_actual
Create Date: 2026-10-15 21:00:00.000000

수현: "이거 매주 있는 거를 전부 삭제 말고 하나씩 삭제할 수 있는 그런 거
없나."

없었다. 블록은 **매주**(weekday) 아니면 **그날 하루**(date) 둘 중
하나이고, 예외라는 개념이 없었다. 그래서 중간고사 때문에 그 주 수업
하나를 빼려면 매주 반복을 통째로 지우는 수밖에 없었다 — 지우면 학기
내내 비는 시간으로 잡힌다.

빠진 날만 따로 적는다. 반복은 그대로 두고 그날만 건너뛴다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0043_block_skip'
down_revision: Union[str, Sequence[str], None] = '0042_step_actual'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'calendar_block_skips',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('block_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('note', sa.Text(), server_default='', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(),
                  nullable=False),
        sa.ForeignKeyConstraint(['block_id'], ['calendar_blocks.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        # 같은 날을 두 번 뺄 일은 없다.
        sa.UniqueConstraint('block_id', 'date', name='uq_block_skip'),
    )
    op.create_index('ix_calendar_block_skips_id', 'calendar_block_skips',
                    ['id'], unique=False)
    op.create_index('ix_calendar_block_skips_date', 'calendar_block_skips',
                    ['date'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_calendar_block_skips_date', 'calendar_block_skips')
    op.drop_index('ix_calendar_block_skips_id', 'calendar_block_skips')
    op.drop_table('calendar_block_skips')
