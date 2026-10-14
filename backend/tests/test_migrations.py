"""The Alembic migrations, not create_all, are what build production databases. These
tests prove the migration history produces exactly the schema the models describe."""

from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import create_engine, inspect

from alembic import command
from app.core.database import Base

BACKEND = Path(__file__).resolve().parents[1]


@pytest.fixture
def migrated(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrations.db'}"
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    engine = create_engine(url)
    yield engine, config
    engine.dispose()


def table_names(engine) -> set[str]:
    with engine.connect() as connection:
        return set(inspect(connection).get_table_names())


def test_upgrade_creates_every_table(migrated):
    engine, _ = migrated
    assert {"books", "members", "loans", "holds", "alembic_version"} <= table_names(engine)


def test_migrations_match_the_models(migrated):
    engine, _ = migrated
    with engine.connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []


def test_downgrade_removes_everything(migrated):
    engine, config = migrated
    command.downgrade(config, "base")
    assert table_names(engine) == {"alembic_version"}
