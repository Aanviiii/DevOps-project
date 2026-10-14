"""The demo seed replays a month of desk activity through the real rules."""

from app.seed import BOOKS, MEMBERS, seed_once


def test_seed_fills_an_empty_library(client):
    message = seed_once()
    assert message.startswith(f"Seeded {len(BOOKS)} books, {len(MEMBERS)} members")

    stats = client.get("/api/stats").json()
    assert stats["titles"] == len(BOOKS)
    assert stats["members_active"] == len(MEMBERS)
    assert sum(day["count"] for day in stats["checkouts_by_day"]) > 0


def test_seed_never_runs_twice(client):
    seed_once()
    assert seed_once() == "Database already has books; skipping seed."
    assert client.get("/api/stats").json()["titles"] == len(BOOKS)


def test_seeded_history_obeys_the_lending_rules(client):
    seed_once()
    # Nobody may hold more books than their tier allows, even after a month of activity.
    for member in client.get("/api/members").json():
        account = client.get(f"/api/members/{member['id']}/account").json()
        assert len(account["active_loans"]) <= account["policy"]["max_active_loans"]
