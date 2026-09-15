"""테스트 공용 설정.

app.database 가 임포트 시점에 URL 을 읽으므로,
app 을 임포트하기 전에 환경변수를 먼저 세팅해야 한다.
"""

import os
import tempfile

TEST_DB_PATH = os.path.join(tempfile.mkdtemp(), "career_os_test.db")
os.environ["CAREER_OS_DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app import models
from app.services import opportunity as opportunity_service  # noqa: E402
from app.database import Base, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def db_session(tmp_path):
    """테스트마다 완전히 새 DB 를 쓴다."""
    engine = create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )

    Base.metadata.create_all(bind=engine)

    TestingSession = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
    )

    session = TestingSession()

    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture
def client(db_session):
    """db_session 과 같은 DB 를 바라보는 API 클라이언트."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # 컨텍스트 매니저로 열지 않으면 lifespan(스케줄러)이 뜨지 않는다.
    test_client = TestClient(app)

    try:
        yield test_client
    finally:
        app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def no_real_collector_keys(monkeypatch):
    """테스트는 바깥 채용 API 를 부르지 않는다.

    app.collector 가 임포트될 때 load_dotenv 로 backend/.env 를 읽는다. 거기에
    진짜 고용24 키가 들어오자, 자동화를 도는 테스트가 실제로 공채속보 264건과 상세를
    부르다 5분을 넘겼다. 키가 필요한 테스트는 monkeypatch.setenv 로 가짜 키를 넣는다.
    """
    for name in ("WORK24_API_KEY", "SARAMIN_API_KEY"):
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def seed_skill(db_session):
    """스킬 하나를 만들어 주는 헬퍼."""

    def _make(name, level=0, category="backend"):
        skill = models.Skill(name=name, category=category, level=level)
        db_session.add(skill)
        db_session.commit()
        db_session.refresh(skill)
        return skill

    return _make


@pytest.fixture
def seed_job(db_session):
    def _make(title="Data Scientist Intern", skills=()):
        job = models.Job(
            company="Test Co",
            title=title,
            role="data_scientist",
        )
        job.skills.extend(skills)
        db_session.add(job)
        db_session.flush()

        # API 의 POST /jobs 와 같은 일을 한다.
        # 수요 집계의 모수는 Opportunity 하나이므로, Job 만 만들면
        # 이 픽스처가 만든 "수요" 가 어디에도 안 잡힌다.
        opportunity_service.bridge_from_legacy_job(db_session, job)

        db_session.commit()
        db_session.refresh(job)
        return job

    return _make


@pytest.fixture
def seed_project(db_session):
    def _make(name, skills=(), career_related=True, **kwargs):
        project = models.Project(
            name=name,
            career_related=career_related,
            **kwargs,
        )
        project.skills.extend(skills)
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)
        return project

    return _make
