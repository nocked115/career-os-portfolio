"""project purpose

Revision ID: 0031_purpose
Revises: 0030_runs
Create Date: 2026-09-21 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0031_purpose'
down_revision: Union[str, Sequence[str], None] = '0030_runs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('purpose', sa.String(), server_default='evidence', nullable=False)
        )
        # SQLite 는 batch 로 표를 다시 만든다. 그때 career_related 의 NOT NULL 이 빠져
        # 모델과 어긋났다 (tests/test_migrations.py 가 잡았다).
        batch_op.alter_column(
            'career_related', existing_type=sa.Boolean(), nullable=False
        )

    # 지금까지의 구분을 그대로 옮긴다 — 커리어 아님 = 취미.
    op.execute("UPDATE projects SET purpose = 'hobby' WHERE career_related = 0")


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('projects', schema=None) as batch_op:
        batch_op.drop_column('purpose')
