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
def migrated_url(tmp_path):
    url = f"sqlite:///{tmp_path / 'migrations.db'}"
    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    command.upgrade(config, "head")
    yield url, config


def test_upgrade_creates_every_table(migrated_url):
    url, _ = migrated_url
    tables = set(inspect(create_engine(url)).get_table_names())
    assert {"books", "members", "loans", "holds", "alembic_version"} <= tables


def test_migrations_match_the_models(migrated_url):
    url, _ = migrated_url
    with create_engine(url).connect() as connection:
        diff = compare_metadata(MigrationContext.configure(connection), Base.metadata)
    assert diff == []


def test_downgrade_removes_everything(migrated_url):
    url, config = migrated_url
    command.downgrade(config, "base")
    assert set(inspect(create_engine(url)).get_table_names()) == {"alembic_version"}
