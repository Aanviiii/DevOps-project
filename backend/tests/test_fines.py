"""Fines are charged when a late book comes back and stay owed until settled."""

from datetime import date


def account(client, member):
    return client.get(f"/api/members/{member['id']}/account").json()


def test_late_return_charges_a_fine_that_stays_owed(client, clock, make_book, make_member, lend):
    member = make_member(tier="PUBLIC")  # 5/day, no grace
    loan = lend(make_book(), member)  # due 15 Oct
    clock.today = date(2026, 10, 20)
    client.post(f"/api/loans/{loan['id']}/return")

    clock.advance(30)  # time passing after the return does not grow the fine
    assert account(client, member)["outstanding_fines"] == 25
    returned = client.get(f"/api/loans/{loan['id']}").json()
    assert returned["fine_due"] == 25
    assert returned["fine_settled_on"] is None


def test_on_time_return_charges_nothing(client, make_book, make_member, lend):
    member = make_member()
    loan = lend(make_book(), member)
    client.post(f"/api/loans/{loan['id']}/return")
    assert account(client, member)["outstanding_fines"] == 0


def test_unpaid_charged_fines_block_borrowing(client, clock, make_book, make_member, lend):
    member = make_member(tier="PUBLIC")
    loan = lend(make_book(), member)
    clock.today = date(2026, 11, 14)  # 30 days late = 150, the blocking threshold
    client.post(f"/api/loans/{loan['id']}/return")

    response = client.post(
        "/api/loans", json={"book_id": make_book()["id"], "member_id": member["id"]}
    )
    assert response.json()["code"] == "FINES_BLOCK"


def test_settling_clears_charged_fines(client, clock, make_book, make_member, lend):
    member = make_member(tier="PUBLIC")
    loan = lend(make_book(), member)
    clock.today = date(2026, 11, 14)
    client.post(f"/api/loans/{loan['id']}/return")

    receipt = client.post(f"/api/members/{member['id']}/settle-fines").json()
    assert receipt == {"member_id": member["id"], "settled": 150, "outstanding_fines": 0}
    assert account(client, member)["can_borrow"] is True
    assert client.get(f"/api/loans/{loan['id']}").json()["fine_settled_on"] == "2026-11-14"


def test_settling_leaves_fines_on_books_still_out(client, clock, make_book, make_member, lend):
    member = make_member(tier="PUBLIC")
    returned = lend(make_book(), member)
    lend(make_book(), member)  # stays out
    clock.today = date(2026, 10, 17)  # both two days late
    client.post(f"/api/loans/{returned['id']}/return")

    receipt = client.post(f"/api/members/{member['id']}/settle-fines").json()
    assert receipt["settled"] == 10
    assert receipt["outstanding_fines"] == 10


def test_settling_with_nothing_owed(client, make_member):
    member = make_member()
    assert client.post(f"/api/members/{member['id']}/settle-fines").json()["settled"] == 0


def settled_total(client) -> float:
    for line in client.get("/metrics").text.splitlines():
        if line.startswith("shelfwise_fines_settled_rupees_total "):
            return float(line.split()[1])
    return 0.0


def test_unpaid_fines_appear_in_stats_and_metrics(client, clock, make_book, make_member, lend):
    member = make_member(tier="PUBLIC")
    loan = lend(make_book(), member)
    clock.today = date(2026, 10, 17)
    client.post(f"/api/loans/{loan['id']}/return")

    assert client.get("/api/stats").json()["outstanding_fines"] == 10
    before = settled_total(client)  # counters are process-wide, so compare the change
    client.post(f"/api/members/{member['id']}/settle-fines")
    assert settled_total(client) - before == 10
