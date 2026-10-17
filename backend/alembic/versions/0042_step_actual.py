"""학습 단계: 실제로 걸린 시간

Revision ID: 0042_step_actual
Revises: 0041_tidy
Create Date: 2026-10-10 20:00:00.000000

단계를 끝내며 적은 시간을 **그날 할 일 줄에** 나눠 담고 있었다(커밋 141).
그래서 비교가 어긋났다 — 오늘 몫은 30분인데 적은 시간은 주차 전체를
끝낸 5시간이라, 속도 보정이 10배로 잡혔다. 추정이 옳았더라도 같다.
하루치 계획에 주차 전체 시간을 적는 꼴이기 때문이다.

같은 것끼리 비교해야 한다.

  하루 몫   오늘 카드에 적은 시간  ↔  그 할 일의 계획 시간
  단계 전체 단계를 끝내며 적은 시간 ↔  단계의 추정 시간

단계 쪽에 적을 자리가 없어서 하루 줄에 밀어 넣었던 것이다. 자리를 만든다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0042_step_actual'
down_revision: Union[str, Sequence[str], None] = '0041_tidy'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('learning_steps', schema=None) as batch_op:
        batch_op.add_column(sa.Column('actual_minutes', sa.Integer(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('learning_steps', schema=None) as batch_op:
        batch_op.drop_column('actual_minutes')
