"""공고: 지원 자격이 안 되는 까닭

Revision ID: 0039_blocked
Revises: 0038_seg_step
Create Date: 2026-10-07 10:00:00.000000

수현: "공고 중에 석박사 요구조건에 안 맞아서 안 되는 거면 이건 어떻게
처리해야 하는 거야?"

지금까지는 아무 처리도 없었다. 학력은 공고를 붙여넣을 때 "걸림돌" 로 한 번
보여주고 버렸다. 그래서 석사 필수 공고가 학사 가능 공고와 똑같이 한 표를
행사한다.

수현 데이터에서 재 보니 작지 않았다. 수요 공고 72건 중 26건이 석박사를
언급하고, 그게 쏠려 있었다 — Reinforcement Learning 4건 중 4건, 추천시스템
3건 중 3건, Computer Vision 4건 중 3건. 2027-02 학사 졸업으로는 못 가는
자리들이 그 스킬의 수요를 거의 혼자 만들고 있었다. 앱이 거꾸로 그걸
공부하라고 말하는 셈이다.

**자동으로 판별하지 않는다.** 정규식으로 갈라 보니 "필수" 로 확실한 건
2건뿐이고 나머지는 "학사/석사 졸업" · "석사 우대" · 신입공채 일반 문구였다.
잘못 거르면 지원할 수 있는 공고를 잃는다 — 그게 더 나쁘다. 사람이 한 번
정하고 앱이 기억한다.

**지우지 않는다.** 까닭을 적어 두면 "Computer Vision 공고 4건 중 3건이
석사 요구" 를 말할 수 있다. 삭제하면 그 신호까지 사라진다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0039_blocked'
down_revision: Union[str, Sequence[str], None] = '0038_seg_step'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('opportunities', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('blocked_reason', sa.String(), server_default='', nullable=False)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('opportunities', schema=None) as batch_op:
        batch_op.drop_column('blocked_reason')
