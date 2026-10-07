"""자료 조각: 읽고 정리한 한 줄

Revision ID: 0037_seg_note
Revises: 0036_track
Create Date: 2026-10-05 23:00:00.000000

수현: "어디부터 어디 읽고 **정리하기** 이런 식으로 나와야 하는데."

읽은 데를 보여주는 것까지는 됐는데(커밋 120), 읽고 나서 남길 자리가
없었다. 읽기만 하고 아무것도 안 남으면 나중에 "이 책에서 뭘 얻었나" 에
답할 수 없고, 경험 · 포트폴리오로 옮길 재료도 없다.

단계(learning_steps)에는 learning_step_outputs 가, 루틴에는
routine_logs.learned 가 이미 그 자리다. 조각에만 없었다.

끝낼 때 적는다. 그때가 가장 잘 떠오르고, 나중에 다시 열 이유가 줄어든다
(routine_logs.learned 에서 같은 판단을 했다).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0037_seg_note'
down_revision: Union[str, Sequence[str], None] = '0036_track'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('learning_resource_segments', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('note', sa.Text(), server_default='', nullable=False)
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('learning_resource_segments', schema=None) as batch_op:
        batch_op.drop_column('note')
