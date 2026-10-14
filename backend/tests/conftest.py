"""Shared fixtures.

Tests never touch Postgres: the app is pointed at an in-memory SQLite database before it
is imported, every test gets a freshly created schema, and the library's clock is a
fixture the test can move forward to make loans overdue or holds lapse.
"""

import os

os.environ["SHELFWISE_DATABASE_URL"] = "sqlite://"
os.environ["SHELFWISE_APP_VERSION"] = "test"

from collections.abc import Iterator  # noqa: E402
from dataclasses import dataclass  # noqa: E402
from datetime import date, timedelta  # noqa: E402
from itertools import count  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.clock import today as real_today  # noqa: E402
from app.core.database import Base, engine  # noqa: E402
from app.main import app  # noqa: E402

START = date(2026, 10, 1)


@dataclass
class Clock:
    today: date = START

    def advance(self, days: int) -> date:
        self.today += timedelta(days=days)
        return self.today


@pytest.fixture(autouse=True)
def schema() -> Iterator[None]:
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


@pytest.fixture
def clock() -> Iterator[Clock]:
    frozen = Clock()
    app.dependency_overrides[real_today] = lambda: frozen.today
    yield frozen
    app.dependency_overrides.pop(real_today, None)


@pytest.fixture
def client(clock: Clock) -> Iterator[TestClient]:
    with TestClient(app) as test_client:
        yield test_client


_isbn = count(1000)


@pytest.fixture
def make_book(client: TestClient):
    def _make(**overrides) -> dict:
        body = {
            "isbn": f"978-0-00-{next(_isbn):06d}",
            "title": "Test Driven Development",
            "author": "Kent Beck",
            "genre": "Technology",
            "published_year": 2002,
            "copies_total": 1,
        } | overrides
        response = client.post("/api/books", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return _make


_email = count(1)


@pytest.fixture
def make_member(client: TestClient):
    def _make(**overrides) -> dict:
        body = {
            "full_name": "Ananya Rao",
            "email": f"member{next(_email)}@example.com",
            "tier": "STUDENT",
        } | overrides
        response = client.post("/api/members", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return _make


@pytest.fixture
def lend(client: TestClient):
    def _lend(book: dict, member: dict) -> dict:
        response = client.post(
            "/api/loans", json={"book_id": book["id"], "member_id": member["id"]}
        )
        assert response.status_code == 201, response.text
        return response.json()

    return _lend
