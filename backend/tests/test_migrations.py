"""마이그레이션과 모델이 어긋나지 않는지 지키는 테스트.

Mission 021 부터 스키마는 create_all 이 아니라 Alembic 이 관리한다.
누가 모델만 고치고 마이그레이션을 안 만들면 여기서 잡힌다.
"""

import pathlib

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from app.database import Base

BACKEND_DIR = pathlib.Path(__file__).resolve().parents[1]

LEGACY_TABLES = {
    "skills",
    "projects",
    "jobs",
    "learning_resources",
    "project_skills",
    "job_skills",
}

MISSION_021_TABLES = {
    "learning_paths",
    "learning_steps",
    "learning_step_resources",
    "opportunities",
    "experiences",
    "experience_skills",
    "portfolio_entries",
    "applications",
    "application_experience_matches",
    "cover_letter_questions",
    "cover_letter_answers",
}


def _config(db_url):
    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.attributes["sqlalchemy.url"] = db_url

    return config


@pytest.fixture
def migrated_db(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'migrated.db'}"

    command.upgrade(_config(db_url), "head")

    return db_url


def test_upgrade_creates_every_table(migrated_db):
    engine = create_engine(migrated_db)

    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert LEGACY_TABLES <= tables
    assert MISSION_021_TABLES <= tables


def test_migrations_match_models(migrated_db):
    """마이그레이션만 돌린 DB 와 모델 정의 사이에 차이가 없어야 한다."""
    engine = create_engine(migrated_db)

    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(
                connection,
                opts={"compare_type": True},
            )

            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    assert diff == [], f"모델과 마이그레이션이 어긋났습니다: {diff}"


def test_baseline_only_creates_legacy_schema(tmp_path):
    """0001_baseline 은 기존 MVP 스키마만 만들어야 한다.

    이 리비전은 이미 돌아가던 DB 에 stamp 하는 기준점이므로
    여기에 신규 테이블이 섞이면 안 된다.
    """
    db_url = f"sqlite:///{tmp_path / 'baseline.db'}"

    command.upgrade(_config(db_url), "0001_baseline")

    engine = create_engine(db_url)

    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert LEGACY_TABLES <= tables
    assert not (MISSION_021_TABLES & tables)


def test_downgrade_returns_to_empty(tmp_path):
    db_url = f"sqlite:///{tmp_path / 'roundtrip.db'}"
    config = _config(db_url)

    command.upgrade(config, "head")
    command.downgrade(config, "base")

    engine = create_engine(db_url)

    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    assert tables <= {"alembic_version"}
