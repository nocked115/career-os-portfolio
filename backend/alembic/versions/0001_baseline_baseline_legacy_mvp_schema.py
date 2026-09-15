"""baseline: legacy MVP schema

기존 MVP 가 create_all 로 만들어 둔 6개 테이블을 그대로 재현하는 기준점.
이미 운영 중인 DB 에는 `alembic stamp 0001_baseline` 으로 표시만 하고
실제로 실행하지는 않는다. 빈 DB 에서는 이 리비전이 레거시 스키마를 만든다.

Revision ID: 0001_baseline
Revises:
Create Date: Mission 021

"""
from alembic import op
import sqlalchemy as sa


revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_skills_id", "skills", ["id"], unique=False)
    op.create_index("ix_skills_name", "skills", ["name"], unique=True)

    op.create_table(
        "projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("career_related", sa.Boolean(), nullable=True),
        sa.Column("estimated_hours", sa.Integer(), nullable=True),
        sa.Column("progress_percent", sa.Integer(), nullable=True),
        sa.Column("daily_minutes", sa.Integer(), nullable=True),
        sa.Column("target_date", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_projects_id", "projects", ["id"], unique=False)

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("company", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("employment_type", sa.String(), nullable=True),
        sa.Column("url", sa.String(), nullable=True),
        sa.Column("deadline", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_jobs_id", "jobs", ["id"], unique=False)

    op.create_table(
        "learning_resources",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("url", sa.String(), nullable=False),
        sa.Column("resource_type", sa.String(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(), nullable=True),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_learning_resources_id",
        "learning_resources",
        ["id"],
        unique=False,
    )

    op.create_table(
        "project_skills",
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.PrimaryKeyConstraint("project_id", "skill_id"),
    )

    op.create_table(
        "job_skills",
        sa.Column("job_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["jobs.id"]),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"]),
        sa.PrimaryKeyConstraint("job_id", "skill_id"),
    )


def downgrade() -> None:
    op.drop_table("job_skills")
    op.drop_table("project_skills")
    op.drop_index("ix_learning_resources_id", table_name="learning_resources")
    op.drop_table("learning_resources")
    op.drop_index("ix_jobs_id", table_name="jobs")
    op.drop_table("jobs")
    op.drop_index("ix_projects_id", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_skills_name", table_name="skills")
    op.drop_index("ix_skills_id", table_name="skills")
    op.drop_table("skills")
