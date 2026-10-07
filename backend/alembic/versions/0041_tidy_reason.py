"""공고: 치우기가 왜 치웠는지

Revision ID: 0041_tidy
Revises: 0040_actual
Create Date: 2026-10-07 21:00:00.000000

수현: "석사 박사 요건 때문에 마감으로 판단한 건지, 공고가 나랑 안 맞아서
버린 건지 판단하는 거 만들었는지."

반만 만들어져 있었다. 사람이 정한 것에는 까닭이 있다 —
`blocked_reason`(자격 안 됨), `filtered_reason`(내 직무가 아님). 그런데
**앱이 자동으로 치운 것에는 아무것도 없었다.** 중복으로 묶은 줄은 그냥
보관함에 들어갔다.

실제로 그것 때문에 틀린 것을 못 봤다. 카카오 "(Pre-training)" 이
"(Post-training)" 의 중복으로 잘못 묶였는데(커밋 138), 보관함에 까닭이
없으니 수현은 그게 버그인지 마감인지 자격 미달인지 알 길이 없었다.
자동으로 치우기 시작한 이상, 왜 치웠는지는 선택이 아니다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0041_tidy'
down_revision: Union[str, Sequence[str], None] = '0040_actual'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('opportunities', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('tidied_reason', sa.String(), server_default='', nullable=False)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('opportunities', schema=None) as batch_op:
        batch_op.drop_column('tidied_reason')
