"""unify demand: bridge legacy jobs to opportunities

Revision ID: 0013_unify_demand
Revises: 0012_calendar
Create Date: 2026-09-08

수요 집계의 모수를 Opportunity 하나로 모은다.

전에는 Opportunity -> Job 브리지가 job 타입만 넘겨서, 공모전·대외활동이
Job 이 되지 않았다. 그 결과 같은 "수요" 를 두 테이블이 다르게 셌다 —
AWS 가 한쪽에서는 1/1, 다른 쪽에서는 0/3 이었다.

앞으로는 Job 으로 들어온 것도 Opportunity 에 남는다. 이 마이그레이션은
그 이전에 만들어진 Job 들을 뒤늦게 옮긴다.

데이터만 옮긴다. 스키마는 건드리지 않으므로 downgrade 는 옮긴 것을
지운다 — Job 은 그대로 남아 있으므로 되돌려도 잃는 것이 없다.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0013_unify_demand'
down_revision: Union[str, Sequence[str], None] = '0012_calendar'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Opportunity 가 없는 Job 을 옮긴다."""
    connection = op.get_bind()

    jobs = connection.execute(
        sa.text(
            """
            SELECT j.id, j.company, j.title, j.role, j.description,
                   j.url, j.employment_type
            FROM jobs j
            LEFT JOIN opportunities o ON o.legacy_job_id = j.id
            WHERE o.id IS NULL
            """
        )
    ).fetchall()

    for job in jobs:
        result = connection.execute(
            sa.text(
                """
                INSERT INTO opportunities (
                    opportunity_type, title, organization, role, description,
                    source, source_url, employment_type, status, legacy_job_id
                ) VALUES (
                    'job', :title, :organization, :role, :description,
                    'legacy_job', :source_url, :employment_type,
                    'discovered', :legacy_job_id
                )
                """
            ),
            {
                "title": job.title or "",
                "organization": job.company or "",
                "role": job.role or "",
                "description": job.description or "",
                "source_url": job.url or "",
                "employment_type": job.employment_type or "",
                "legacy_job_id": job.id,
            },
        )

        opportunity_id = result.lastrowid

        # 스킬 연결이 곧 수요 집계의 재료다. 이게 빠지면 옮겨도 소용없다.
        connection.execute(
            sa.text(
                """
                INSERT OR IGNORE INTO opportunity_skills
                    (opportunity_id, skill_id)
                SELECT :opportunity_id, skill_id
                FROM job_skills WHERE job_id = :job_id
                """
            ),
            {"opportunity_id": opportunity_id, "job_id": job.id},
        )

    # 이미 연결돼 있던 쌍도 스킬을 맞춘다.
    #
    # 브리지는 Opportunity -> Job 한 방향만 있었기 때문에, Job 쪽에만
    # 붙은 스킬이 생길 수 있었다. 실제로 그런 경우가 있었다 —
    # Job 에는 AWS 가 있는데 짝인 Opportunity 에는 없었고,
    # 모수를 Opportunity 로 옮기는 순간 그 수요가 통째로 사라졌다.
    connection.execute(
        sa.text(
            """
            INSERT OR IGNORE INTO opportunity_skills
                (opportunity_id, skill_id)
            SELECT o.id, js.skill_id
            FROM opportunities o
            JOIN job_skills js ON js.job_id = o.legacy_job_id
            WHERE o.legacy_job_id IS NOT NULL
            """
        )
    )


def downgrade() -> None:
    """이 마이그레이션이 만든 것만 지운다. Job 은 그대로 남는다."""
    connection = op.get_bind()

    connection.execute(
        sa.text(
            """
            DELETE FROM opportunity_skills
            WHERE opportunity_id IN (
                SELECT id FROM opportunities WHERE source = 'legacy_job'
            )
            """
        )
    )
    connection.execute(
        sa.text("DELETE FROM opportunities WHERE source = 'legacy_job'")
    )
