"""profile certificates

Revision ID: 0019_certificates
Revises: 0018_all_day
Create Date: 2026-09-15 20:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0019_certificates'
down_revision: Union[str, Sequence[str], None] = '0018_all_day'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'certificates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('score', sa.String(), server_default='', nullable=False),
        sa.Column('detail', sa.String(), server_default='', nullable=False),
        sa.Column('issuer', sa.String(), server_default='', nullable=False),
        sa.Column('status', sa.String(), server_default='held', nullable=False),
        sa.Column('acquired_on', sa.Date(), nullable=True),
        sa.Column('expires_on', sa.Date(), nullable=True),
        sa.Column('note', sa.Text(), server_default='', nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_certificates_id'), 'certificates', ['id'], unique=False)
    op.create_index(op.f('ix_certificates_category'), 'certificates', ['category'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_certificates_category'), table_name='certificates')
    op.drop_index(op.f('ix_certificates_id'), table_name='certificates')
    op.drop_table('certificates')
