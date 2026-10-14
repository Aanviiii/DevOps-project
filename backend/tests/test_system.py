from app.core.database import get_db
from app.main import app


def test_root_describes_the_service(client):
    body = client.get("/").json()
    assert body == {"service": "Shelfwise API", "version": "test", "docs": "/docs"}


def test_health_is_up(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "UP"}


def test_ready_when_the_database_answers(client):
    assert client.get("/ready").json() == {"status": "READY", "database": "ok"}


def test_not_ready_when_the_database_is_down(client):
    class BrokenSession:
        def execute(self, *_):
            raise ConnectionError("database is down")

    app.dependency_overrides[get_db] = lambda: BrokenSession()
    try:
        response = client.get("/ready")
    finally:
        app.dependency_overrides.pop(get_db)
    assert response.status_code == 503
    assert response.json()["status"] == "NOT_READY"


def test_every_response_names_the_running_version(client):
    assert client.get("/health").headers["X-Shelfwise-Version"] == "test"


def test_openapi_docs_are_published(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert {"/api/books", "/api/members", "/api/loans", "/api/holds", "/api/stats"} <= set(paths)


def test_metrics_expose_http_and_library_series(client, make_book, make_member, lend):
    lend(make_book(), make_member(tier="FACULTY"))
    client.post("/api/loans", json={"book_id": 999, "member_id": 1})  # a refusal

    text = client.get("/metrics").text
    assert 'http_requests_total{handler="/api/loans",method="POST",status="201"}' in text
    assert 'shelfwise_checkouts_total{tier="FACULTY"}' in text
    assert 'shelfwise_circulation_refusals_total{code="BOOK_NOT_FOUND"}' in text
    assert "shelfwise_books_on_loan 1.0" in text
    assert 'shelfwise_build_info{version="test"} 1.0' in text


def test_probes_are_not_counted_as_traffic(client):
    client.get("/health")
    assert 'handler="/health"' not in client.get("/metrics").text


def test_stats_on_an_empty_library(client):
    stats = client.get("/api/stats").json()
    assert stats["titles"] == 0
    assert stats["on_loan"] == 0
    assert len(stats["checkouts_by_day"]) == 14
    assert stats["popular_genres"] == []


def test_stats_summarise_the_collection(client, clock, make_book, make_member, lend):
    member = make_member(tier="PUBLIC")
    lend(make_book(genre="Fiction", copies_total=2), member)
    lend(make_book(genre="Fiction"), member)
    make_book(genre="History", copies_total=4)
    clock.advance(15)  # 16 Oct: both loans (due 15 Oct) are a day late

    stats = client.get("/api/stats").json()
    assert (stats["titles"], stats["copies"], stats["on_loan"]) == (3, 7, 2)
    assert stats["overdue"] == 2
    assert stats["outstanding_fines"] == 10  # 2 loans x 1 day x 5 rupees
    assert stats["popular_genres"] == [{"genre": "Fiction", "loans": 2}]
    assert stats["checkouts_by_day"][-1]["day"] == "2026-10-16"
