from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from app.database import DATABASE_URL, Base
from app import models  # noqa: F401  -- 모든 모델을 metadata 에 등록하기 위해 필요

config = context.config

# 접속 정보는 app.database 를 단일 출처로 사용한다.
# 테스트에서는 Config.attributes 로 임시 DB 를 주입할 수 있다.
DB_URL = config.attributes.get("sqlalchemy.url") or DATABASE_URL

config.set_main_option("sqlalchemy.url", DB_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _is_sqlite() -> bool:
    return DB_URL.startswith("sqlite")


def run_migrations_offline() -> None:
    context.configure(
        url=DB_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        # SQLite 는 ALTER 지원이 약해서 batch 모드가 필요하다.
        render_as_batch=_is_sqlite(),
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            render_as_batch=_is_sqlite(),
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
