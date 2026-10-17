"""생각 · 고민 · 아이디어를 모아 두는 자리

Revision ID: 0044_thoughts
Revises: 0043_block_skip
Create Date: 2026-10-16 10:00:00.000000

수현: "요즘 생각 고민이나 이런 거, 대학원을 갈지 말지 고민하는 거
얘는 모르잖아."

맞다. 앱은 할 일 · 공고 · 스킬 · 증거를 안다. 그런데 **무엇을 고민
중인지는 어디에도 없다.** 그게 가장 큰 결정인데도 그렇다 — 대학원을
갈지 말지는 앞으로 2년을 가르는 질문이고, 앱이 가진 데이터(석박사
요건에 막힌 공고가 몇 건인지)가 바로 그 질문에 답하는 재료다. 그런데
질문이 적힌 자리가 없으니 재료와 만날 일이 없었다.

여러 세션에 흩어지는 것도 같은 문제다. 수업 들으며 나온 생각, 공부하다
떠오른 아이디어가 그 대화 안에서 끝난다. 적어 둘 한 곳이 필요하다.

세 가지로 나눈다.

  question  아직 못 정한 것. 열려 있는 동안 계속 보인다.
  idea      해 볼 만한 것. 프로젝트가 되면 닫는다.
  note      그냥 적어 두는 것.

**닫을 때 무엇으로 정했는지 적는다.** 고민을 지우기만 하면 반 년 뒤
같은 고민을 처음부터 다시 한다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0044_thoughts'
down_revision: Union[str, Sequence[str], None] = '0043_block_skip'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'thoughts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('kind', sa.String(), server_default='question', nullable=False),
        sa.Column('body', sa.Text(), nullable=False),
        # 어디서 나온 생각인지. "추천시스템 수업", "다비 회고" 처럼 한마디.
        sa.Column('source', sa.String(), server_default='', nullable=False),
        sa.Column('status', sa.String(), server_default='open', nullable=False),
        # 무엇으로 정했는지. 닫을 때만 채운다.
        sa.Column('decision', sa.Text(), server_default='', nullable=False),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(),
                  nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(),
                  nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_thoughts_id', 'thoughts', ['id'], unique=False)
    op.create_index('ix_thoughts_kind', 'thoughts', ['kind'], unique=False)
    op.create_index('ix_thoughts_status', 'thoughts', ['status'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_thoughts_status', 'thoughts')
    op.drop_index('ix_thoughts_kind', 'thoughts')
    op.drop_index('ix_thoughts_id', 'thoughts')
    op.drop_table('thoughts')
