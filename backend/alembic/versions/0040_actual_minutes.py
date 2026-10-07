"""계획 한 줄: 실제로 걸린 시간과 못 한 까닭

Revision ID: 0040_actual
Revises: 0039_blocked
Create Date: 2026-10-07 20:00:00.000000

수현: "실제 걸리는 시간을 적는 칸을 줄 수 있을까? 아니면 못 한 이유라도.
시간을 넣으면 그 학습 시간에 맞춰서 해줄 수 있잖아."

앱은 "180분" 이라고 적어 두고 **실제로 얼마나 걸렸는지 한 번도 묻지
않았다.** 그러니 추정이 영원히 안 맞는다. 오늘 몫을 자르는 것도(1번부터
5번까지), 구간 속도를 내는 것도(하루 53분) 전부 그 틀린 추정 위에 서 있다.

  actual_minutes  끝낼 때 적는 실제 시간. 비면 안 적은 것이다.
  skip_reason     넘길 때 적는 까닭. 안 한 것도 기록이다.

둘 다 비워 둘 수 있다. 적어야만 끝낼 수 있게 하면 적기 싫어서 안 끝내게
된다 — 그러면 기록이 더 나빠진다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0040_actual'
down_revision: Union[str, Sequence[str], None] = '0039_blocked'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('daily_plan_tasks', schema=None) as batch_op:
        batch_op.add_column(sa.Column('actual_minutes', sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column('skip_reason', sa.String(), server_default='', nullable=False)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('daily_plan_tasks', schema=None) as batch_op:
        batch_op.drop_column('skip_reason')
        batch_op.drop_column('actual_minutes')
