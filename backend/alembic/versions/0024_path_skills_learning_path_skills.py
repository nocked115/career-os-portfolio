"""learning path skills (many to many)

Revision ID: 0024_path_skills
Revises: 0023_plan_focus
Create Date: 2026-09-16 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0024_path_skills'
down_revision: Union[str, Sequence[str], None] = '0023_plan_focus'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'learning_path_skills',
        sa.Column('learning_path_id', sa.Integer(), nullable=False),
        sa.Column('skill_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['learning_path_id'], ['learning_paths.id']),
        sa.ForeignKeyConstraint(['skill_id'], ['skills.id']),
        sa.PrimaryKeyConstraint('learning_path_id', 'skill_id'),
    )

    # 지금까지의 대표 스킬을 연결로 옮긴다. 옮기지 않으면 이미 만든 경로가
    # 어떤 스킬도 키우지 않는 것처럼 보인다.
    op.execute(
        "INSERT INTO learning_path_skills (learning_path_id, skill_id) "
        "SELECT id, skill_id FROM learning_paths WHERE skill_id IS NOT NULL"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('learning_path_skills')
