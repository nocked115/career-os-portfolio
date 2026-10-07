"""skill: 전공(도구) · 교양(배경지식) 구분

Revision ID: 0036_track
Revises: 0035_portfolio
Create Date: 2026-10-05 16:00:00.000000

수현: "대학교의 교양과 전공처럼 — CS 지식 이런 것들은 교양쪽으로,
책 읽고 정리하기 이 정도."

순위표가 둘을 같은 줄에 세우고 있었다. 그래서 "Infrastructure" 가 수요
21% 로 5위에 올라와 오늘 할 일을 밀어내는데, 정작 그걸 보고 무엇을
공부해야 할지는 알 수 없다. 공고에서 실제로 세어지는 건 GCP 9건,
BigQuery 7건, Kubernetes 4건 같은 **구체적인 도구**다.

도구는 손에 익히는 것이고 배경지식은 읽고 아는 것이다. 둘을 한 줄에
세우면 "다음에 뭘 할까" 의 답이 안 나온다. 칸을 나눈다.

기본값은 major 다. 지금 있는 것은 전부 도구로 넣어 둔 것이고, 교양으로
내리는 건 사람이 보고 정하는 일이다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0036_track'
down_revision: Union[str, Sequence[str], None] = '0035_portfolio'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('skills', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('track', sa.String(), server_default='major', nullable=False)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('skills', schema=None) as batch_op:
        batch_op.drop_column('track')
