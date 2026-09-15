"""mission 022: learning resource importance

Revision ID: 0003_mission022
Revises: 0002_mission021
Create Date: 2026-09-02 10:45:06.113187

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0003_mission022'
down_revision: Union[str, Sequence[str], None] = '0002_mission021'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """중요도 컬럼 추가 + 기존 resource_type 값 정리."""
    with op.batch_alter_table("learning_resources", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "importance",
                sa.String(),
                server_default="primary",
                nullable=False,
            )
        )

    # Mission 022 이전 기본값이었던 "youtube" 를 열거값 "video" 로 옮긴다.
    # 이 값은 ResourceType Literal 에 없어서 그대로 두면 수정 요청이 422 로 막힌다.
    op.execute(
        "UPDATE learning_resources "
        "SET resource_type = 'video' "
        "WHERE resource_type = 'youtube'"
    )


def downgrade() -> None:
    """중요도 컬럼만 되돌린다.

    resource_type 은 'video' 로 남겨둔다.
    'youtube' 로 되돌리면 이 마이그레이션 이후에 정상적으로 등록된
    'video' 자료까지 함께 망가지기 때문이다.
    """
    with op.batch_alter_table("learning_resources", schema=None) as batch_op:
        batch_op.drop_column("importance")
