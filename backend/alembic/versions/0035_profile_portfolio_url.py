"""profile: 포트폴리오 주소

Revision ID: 0035_portfolio
Revises: 0034_prefs
Create Date: 2026-09-30 12:00:00.000000

지원서마다 내는 포트폴리오 주소를 둘 칸이 없었다. github_url 은 깃허브 프로필,
blog_url 은 블로그라 둘 다 다른 것이고, 포트폴리오 항목(portfolio_entries)은
프로젝트 하나하나를 담는 표다. 지원할 때 매번 찾지 않게 프로필에 둔다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0035_portfolio'
down_revision: Union[str, Sequence[str], None] = '0034_prefs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('portfolio_url', sa.String(), server_default='', nullable=False)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('profiles', schema=None) as batch_op:
        batch_op.drop_column('portfolio_url')
