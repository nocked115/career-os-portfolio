"""알리미 — 날짜가 있는 것을 한 판에

Revision ID: 0045_reminders
Revises: 0044_thoughts
Create Date: 2026-10-17 14:00:00.000000

수현: "뭔가 오늘 할 일에 들어가는 거 말고 이거 좀 게시판처럼 만들고
싶은데. 오늘 마감 · 역량검사 대비 (10/18 일) 이런 것도
알리미처럼 넣으려고."

두 번 틀렸다. 처음엔 오늘 계획 위에 얹었고(커밋 155), 다음엔 생각
적는 자리에 넣으려 했다. 둘 다 아니다.

**이건 일을 시키는 판이 아니라 알려 주는 판이다.** 시간을 재지 않고,
진행률을 움직이지 않고, 오늘 예산을 먹지 않는다. 날짜가 오면 알려
주고 지나가면 사라진다.

그리고 알릴 것의 **대부분은 앱이 이미 안다** — 공고 마감, 지원서 마감,
시험일, 학습 단계 마감. 흩어져 있었을 뿐이다. 모아서 한 줄로 세우고,
앱이 모르는 것만 사람이 적는다. 이 표는 그 적는 것만 담는다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0045_reminders'
down_revision: Union[str, Sequence[str], None] = '0044_thoughts'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'reminders',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('due', sa.Date(), nullable=False),
        # 몇 시에. 없으면 그냥 그날.
        sa.Column('at', sa.String(), server_default='', nullable=False),
        sa.Column('note', sa.Text(), server_default='', nullable=False),
        sa.Column('done', sa.Boolean(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(),
                  nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_reminders_id', 'reminders', ['id'], unique=False)
    op.create_index('ix_reminders_due', 'reminders', ['due'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_reminders_due', 'reminders')
    op.drop_index('ix_reminders_id', 'reminders')
    op.drop_table('reminders')
