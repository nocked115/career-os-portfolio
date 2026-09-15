import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# 기본값은 기존과 동일한 로컬 SQLite.
# 테스트나 향후 PostgreSQL 전환 시 환경변수로만 바꿀 수 있게 한다.
DATABASE_URL = os.getenv(
    "CAREER_OS_DATABASE_URL",
    "sqlite:///./career_os.db",
)

connect_args = {}

if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args
)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

Base = declarative_base()


def get_db():
    """FastAPI 의존성. 라우터와 main.py 가 함께 쓴다."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
