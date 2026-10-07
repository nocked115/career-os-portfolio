"""favorite · project idea · path kind · preferred companies

Revision ID: 0034_prefs
Revises: 0033_log_learned
Create Date: 2026-09-27 12:00:00.000000

네 가지를 한 번에 넣는다 — 전부 "무엇을 먼저 할지" 를 판단하는 재료다.

  opportunities.favorite    즐겨찾기. 켜두면 화면 배지로 알린다.
  projects.why              왜 이 프로젝트를 하려는가. 공고에 쓸지 판단하는 근거가 된다.
  learning_paths.kind       학교 수업(course) 인가 따로 공부(self) 인가. 오늘 할 일을 갈래로 묶는다.
  preferred_companies       가고 싶은 회사. 매칭 점수에 얹는다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0034_prefs'
down_revision: Union[str, Sequence[str], None] = '0033_log_learned'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('opportunities', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('favorite', sa.Boolean(), server_default='0', nullable=False)
        )

    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('why', sa.Text(), server_default='', nullable=False)
        )

    with op.batch_alter_table('learning_paths', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('kind', sa.String(), server_default='self', nullable=False)
        )

    op.create_table(
        'preferred_companies',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('note', sa.Text(), server_default='', nullable=False),
        sa.Column('rank', sa.Integer(), server_default='2', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name', name='uq_preferred_company'),
    )
    op.create_index(
        op.f('ix_preferred_companies_id'), 'preferred_companies', ['id'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_preferred_companies_id'), table_name='preferred_companies')
    op.drop_table('preferred_companies')

    with op.batch_alter_table('learning_paths', schema=None) as batch_op:
        batch_op.drop_column('kind')

    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('why')

    with op.batch_alter_table('opportunities', schema=None) as batch_op:
        batch_op.drop_column('favorite')
