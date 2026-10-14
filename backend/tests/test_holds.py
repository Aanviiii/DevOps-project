def place(client, book, member):
    return client.post("/api/holds", json={"book_id": book["id"], "member_id": member["id"]})


def checkout(client, book, member):
    return client.post("/api/loans", json={"book_id": book["id"], "member_id": member["id"]})


def lent_out_book(make_book, make_member, lend):
    """A single-copy book that is currently on loan, and the loan."""
    book = make_book(copies_total=1)
    loan = lend(book, make_member())
    return book, loan


def test_hold_is_refused_while_a_copy_is_on_the_shelf(client, make_book, make_member):
    response = place(client, make_book(copies_total=1), make_member())
    assert response.status_code == 409
    assert response.json()["code"] == "HOLD_NOT_NEEDED"


def test_holds_queue_in_order(client, make_book, make_member, lend):
    book, _ = lent_out_book(make_book, make_member, lend)
    first = place(client, book, make_member()).json()
    second = place(client, book, make_member()).json()

    assert first["status"] == "WAITING"
    assert (first["queue_position"], second["queue_position"]) == (1, 2)
    assert client.get(f"/api/books/{book['id']}").json()["holds_waiting"] == 2


def test_member_cannot_queue_twice_or_for_a_book_they_have(client, make_book, make_member, lend):
    book = make_book(copies_total=1)
    borrower, waiter = make_member(), make_member()
    lend(book, borrower)
    place(client, book, waiter)

    assert place(client, book, waiter).json()["code"] == "DUPLICATE_HOLD"
    assert place(client, book, borrower).json()["code"] == "ALREADY_BORROWED"


def test_inactive_member_cannot_place_a_hold(client, make_book, make_member, lend):
    book, _ = lent_out_book(make_book, make_member, lend)
    member = make_member()
    client.put(f"/api/members/{member['id']}", json={"active": False})
    assert place(client, book, member).json()["code"] == "MEMBER_INACTIVE"


def test_return_sets_the_copy_aside_for_the_first_in_line(client, make_book, make_member, lend):
    book, loan = lent_out_book(make_book, make_member, lend)
    first = place(client, book, make_member()).json()
    second = place(client, book, make_member()).json()

    client.post(f"/api/loans/{loan['id']}/return")
    holds = {h["id"]: h for h in client.get("/api/holds").json()}

    assert holds[first["id"]]["status"] == "READY"
    assert holds[first["id"]]["ready_until"] == "2026-10-04"
    assert holds[second["id"]]["queue_position"] == 1
    assert client.get(f"/api/books/{book['id']}").json()["copies_available"] == 0


def test_copy_on_the_hold_shelf_goes_only_to_its_holder(client, make_book, make_member, lend):
    book, loan = lent_out_book(make_book, make_member, lend)
    holder, stranger = make_member(), make_member()
    hold = place(client, book, holder).json()
    client.post(f"/api/loans/{loan['id']}/return")

    assert checkout(client, book, stranger).json()["code"] == "NOT_AVAILABLE"
    assert checkout(client, book, holder).status_code == 201
    fulfilled = client.get("/api/holds", params={"status": "FULFILLED"}).json()
    assert [h["id"] for h in fulfilled] == [hold["id"]]


def test_uncollected_hold_expires_and_passes_on(client, clock, make_book, make_member, lend):
    book, loan = lent_out_book(make_book, make_member, lend)
    first = place(client, book, make_member()).json()
    second = place(client, book, make_member()).json()
    client.post(f"/api/loans/{loan['id']}/return")  # first is READY until 4 Oct

    clock.advance(4)  # 5 Oct: first never came
    holds = {h["id"]: h for h in client.get("/api/holds").json()}

    assert first["id"] not in holds
    assert holds[second["id"]]["status"] == "READY"
    expired = client.get("/api/holds", params={"status": "EXPIRED"}).json()
    assert [h["id"] for h in expired] == [first["id"]]


def test_cancelling_a_ready_hold_readies_the_next(client, make_book, make_member, lend):
    book, loan = lent_out_book(make_book, make_member, lend)
    first = place(client, book, make_member()).json()
    second = place(client, book, make_member()).json()
    client.post(f"/api/loans/{loan['id']}/return")

    cancelled = client.post(f"/api/holds/{first['id']}/cancel").json()
    assert cancelled["status"] == "CANCELLED"
    statuses = {h["id"]: h["status"] for h in client.get("/api/holds").json()}
    assert statuses == {second["id"]: "READY"}


def test_closed_hold_cannot_be_cancelled_again(client, make_book, make_member, lend):
    book, _ = lent_out_book(make_book, make_member, lend)
    hold = place(client, book, make_member()).json()
    client.post(f"/api/holds/{hold['id']}/cancel")
    response = client.post(f"/api/holds/{hold['id']}/cancel")
    assert response.json()["code"] == "HOLD_CLOSED"


def test_holds_can_be_filtered_by_member(client, make_book, make_member, lend):
    book, _ = lent_out_book(make_book, make_member, lend)
    me, other = make_member(), make_member()
    place(client, book, me)
    place(client, book, other)
    mine = client.get("/api/holds", params={"member_id": me["id"]}).json()
    assert [h["member_id"] for h in mine] == [me["id"]]


# ---------------------------------------------------------------- renewals vs. the queue


def test_renewal_is_refused_while_others_wait(client, make_book, make_member, lend):
    book, loan = lent_out_book(make_book, make_member, lend)
    place(client, book, make_member())

    response = client.post(f"/api/loans/{loan['id']}/renew")
    assert response.status_code == 409
    assert response.json()["code"] == "HELD_FOR_OTHERS"


def test_renewal_is_allowed_again_once_the_queue_empties(client, make_book, make_member, lend):
    book, loan = lent_out_book(make_book, make_member, lend)
    hold = place(client, book, make_member()).json()
    client.post(f"/api/holds/{hold['id']}/cancel")

    assert client.post(f"/api/loans/{loan['id']}/renew").status_code == 200


def test_spare_copies_do_not_block_renewal(client, make_book, make_member, lend):
    # Two copies, both out, one member waiting: the next copy returned serves them,
    # so the borrower holding the *other* copy is still blocked; but once a copy is
    # back on the shelf for the waiter, renewing is fine.
    book = make_book(copies_total=2)
    first, second = lend(book, make_member()), lend(book, make_member())
    place(client, book, make_member())
    client.post(f"/api/loans/{first['id']}/return")  # the waiter's copy is now READY

    assert client.post(f"/api/loans/{second['id']}/renew").status_code == 200
