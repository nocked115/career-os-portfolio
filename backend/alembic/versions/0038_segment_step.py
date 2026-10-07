"""자료 조각이 어느 학습 단계를 덮는가

Revision ID: 0038_seg_step
Revises: 0037_seg_note
Create Date: 2026-10-06 12:00:00.000000

수현: "내가 학습 완료 누르면 그 해당 챕터가 완료되었다고 판정되려고 하는데."

지금까지 연결은 **자료 단위**뿐이었다 (learning_step_resources: 단계 ↔ 책).
"3주차는 핸즈온 4장" 같은 **장 단위**를 적을 자리가 없어서, 단계를 끝내도
그 장이 그대로 남았다. 같은 공부를 두 군데서 따로 체크하게 된다.

조각 하나는 단계 하나에만 속한다 — 4장을 3주차와 5주차가 같이 덮는 일은
없다. 그래서 다대다가 아니라 FK 하나로 둔다.

nullable 이다. 어느 단계에도 안 붙은 조각이 정상이다 — 수업과 무관하게
혼자 읽는 책이 그렇다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0038_seg_step'
down_revision: Union[str, Sequence[str], None] = '0037_seg_note'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('learning_resource_segments', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('learning_step_id', sa.Integer(), nullable=True)
        )
        batch_op.create_foreign_key(
            'fk_segment_learning_step',
            'learning_steps',
            ['learning_step_id'],
            ['id'],
        )
        batch_op.create_index(
            'ix_learning_resource_segments_learning_step_id',
            ['learning_step_id'],
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('learning_resource_segments', schema=None) as batch_op:
        batch_op.drop_index('ix_learning_resource_segments_learning_step_id')
        batch_op.drop_constraint('fk_segment_learning_step', type_='foreignkey')
        batch_op.drop_column('learning_step_id')
