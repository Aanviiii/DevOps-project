from datetime import date


def checkout(client, book, member):
    return client.post("/api/loans", json={"book_id": book["id"], "member_id": member["id"]})


def test_checkout_sets_due_date_from_member_tier(client, make_book, make_member):
    student = checkout(client, make_book(), make_member(tier="STUDENT")).json()
    faculty = checkout(client, make_book(), make_member(tier="FACULTY")).json()

    assert student["checked_out_on"] == "2026-10-01"
    assert student["due_on"] == "2026-10-15"
    assert faculty["due_on"] == "2026-10-29"


def test_checkout_reduces_copies_available(client, make_book, make_member, lend):
    book = make_book(copies_total=2)
    lend(book, make_member())
    assert client.get(f"/api/books/{book['id']}").json()["copies_available"] == 1


def test_last_copy_cannot_be_lent_twice(client, make_book, make_member, lend):
    book = make_book(copies_total=1)
    lend(book, make_member())
    response = checkout(client, book, make_member())
    assert response.status_code == 409
    assert response.json()["code"] == "NOT_AVAILABLE"


def test_loan_limit_depends_on_tier(client, make_book, make_member, lend):
    public = make_member(tier="PUBLIC")  # 3 books at a time
    for _ in range(3):
        lend(make_book(), public)
    response = checkout(client, make_book(), public)
    assert response.json()["code"] == "LOAN_LIMIT"


def test_inactive_member_cannot_borrow(client, make_book, make_member):
    member = make_member()
    client.put(f"/api/members/{member['id']}", json={"active": False})
    assert checkout(client, make_book(), member).json()["code"] == "MEMBER_INACTIVE"


def test_member_cannot_borrow_two_copies_of_one_book(client, make_book, make_member, lend):
    book, member = make_book(copies_total=5), make_member()
    lend(book, member)
    assert checkout(client, book, member).json()["code"] == "DUPLICATE_LOAN"


def test_unknown_book_or_member_is_404(client, make_book, make_member):
    assert checkout(client, {"id": 999}, make_member()).status_code == 404
    assert checkout(client, make_book(), {"id": 999}).status_code == 404


def test_return_frees_the_copy(client, make_book, make_member, lend):
    book = make_book()
    loan = lend(book, make_member())
    response = client.post(f"/api/loans/{loan['id']}/return")
    assert response.status_code == 200
    assert response.json()["returned_on"] == "2026-10-01"
    assert client.get(f"/api/books/{book['id']}").json()["copies_available"] == 1


def test_a_loan_can_only_be_returned_once(client, make_book, make_member, lend):
    loan = lend(make_book(), make_member())
    client.post(f"/api/loans/{loan['id']}/return")
    response = client.post(f"/api/loans/{loan['id']}/return")
    assert response.status_code == 409
    assert response.json()["code"] == "ALREADY_RETURNED"


def test_late_return_records_the_fine(client, clock, make_book, make_member, lend):
    loan = lend(make_book(), make_member(tier="STUDENT"))  # due 15 Oct, 1 day grace, 2/day
    clock.today = date(2026, 10, 25)  # 10 days late, 9 chargeable
    returned = client.post(f"/api/loans/{loan['id']}/return").json()
    assert returned["days_overdue"] == 10
    assert returned["fine_due"] == 18


def test_renewal_extends_the_loan(client, clock, make_book, make_member, lend):
    loan = lend(make_book(), make_member(tier="STUDENT"))
    clock.advance(10)
    renewed = client.post(f"/api/loans/{loan['id']}/renew").json()
    assert renewed["renewals"] == 1
    assert renewed["due_on"] == "2026-10-29"  # 14 days from the old due date (15 Oct)


def test_renewal_limit(client, make_book, make_member, lend):
    loan = lend(make_book(), make_member(tier="PUBLIC"))  # one renewal allowed
    assert client.post(f"/api/loans/{loan['id']}/renew").status_code == 200
    response = client.post(f"/api/loans/{loan['id']}/renew")
    assert response.json()["code"] == "RENEWAL_LIMIT"


def test_returned_loan_cannot_be_renewed(client, make_book, make_member, lend):
    loan = lend(make_book(), make_member())
    client.post(f"/api/loans/{loan['id']}/return")
    assert client.post(f"/api/loans/{loan['id']}/renew").json()["code"] == "ALREADY_RETURNED"


def test_overdue_filter_lists_only_late_loans(client, clock, make_book, make_member, lend):
    member = make_member(tier="FACULTY")
    early = lend(make_book(title="Early"), member)  # due 29 Oct
    clock.today = date(2026, 10, 20)
    lend(make_book(title="Later"), member)  # due 17 Nov
    clock.today = date(2026, 11, 1)

    overdue = client.get("/api/loans", params={"state": "overdue"}).json()
    assert [loan["id"] for loan in overdue] == [early["id"]]
    assert overdue[0]["days_overdue"] == 3


def test_list_filters_returned_and_by_member(client, make_book, make_member, lend):
    alice, bob = make_member(), make_member()
    first = lend(make_book(), alice)
    lend(make_book(), bob)
    client.post(f"/api/loans/{first['id']}/return")

    returned = client.get("/api/loans", params={"state": "returned"}).json()
    assert [loan["id"] for loan in returned] == [first["id"]]
    assert len(client.get("/api/loans", params={"state": "all"}).json()) == 2
    assert len(client.get("/api/loans", params={"member_id": bob["id"]}).json()) == 1


def test_get_single_loan(client, make_book, make_member, lend):
    loan = lend(make_book(title="Solo"), make_member(full_name="Isha"))
    fetched = client.get(f"/api/loans/{loan['id']}").json()
    assert fetched["book_title"] == "Solo"
    assert fetched["member_name"] == "Isha"
    assert client.get("/api/loans/999").status_code == 404


def test_unpaid_fines_block_new_checkouts(client, clock, make_book, make_member, lend):
    member = make_member(tier="PUBLIC")  # 5/day, no grace, cap 200, block at 150
    lend(make_book(), member)
    clock.today = date(2026, 11, 14)  # due 15 Oct: 30 days late = 150

    account = client.get(f"/api/members/{member['id']}/account").json()
    assert account["outstanding_fines"] == 150
    assert account["can_borrow"] is False
    assert checkout(client, make_book(), member).json()["code"] == "FINES_BLOCK"
