from logging.config import fileConfig

from sqlalchemy import create_engine, text

from alembic import context
from app import models  # noqa: F401  (registers every table on Base.metadata)
from app.core.config import get_settings
from app.core.database import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# Any fixed number works; every replica must use the same one.
MIGRATION_LOCK_ID = 7_441_001


def database_url() -> str:
    # Tests pass an explicit URL through the Alembic config; containers use settings.
    return config.get_main_option("sqlalchemy.url") or get_settings().database_url


def run_migrations_offline() -> None:
    context.configure(url=database_url(), target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url())
    with engine.connect() as connection:
        is_postgres = connection.dialect.name == "postgresql"
        if is_postgres:
            # Several backend replicas start at once in Kubernetes and each runs
            # `alembic upgrade head`. The advisory lock makes them take turns, so only the
            # first one migrates and the rest find the schema already at head.
            connection.execute(text("SELECT pg_advisory_lock(:id)"), {"id": MIGRATION_LOCK_ID})
            connection.commit()
        try:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=connection.dialect.name == "sqlite",
                compare_type=True,
            )
            with context.begin_transaction():
                context.run_migrations()
        finally:
            if is_postgres:
                connection.execute(
                    text("SELECT pg_advisory_unlock(:id)"), {"id": MIGRATION_LOCK_ID}
                )
                connection.commit()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
