def test_new_member_gets_a_card_number(client):
    response = client.post(
        "/api/members",
        json={"full_name": "Kabir Shah", "email": "kabir@example.com", "tier": "FACULTY"},
    )
    assert response.status_code == 201
    member = response.json()
    assert member["card_number"] == f"SW-{member['id']:06d}"
    assert member["tier"] == "FACULTY"
    assert member["active"] is True


def test_tier_defaults_to_public(client):
    response = client.post("/api/members", json={"full_name": "Zoya", "email": "z@example.com"})
    assert response.json()["tier"] == "PUBLIC"


def test_duplicate_email_is_a_conflict(client, make_member):
    member = make_member()
    response = client.post(
        "/api/members", json={"full_name": "Someone Else", "email": member["email"]}
    )
    assert response.status_code == 409
    assert response.json()["code"] == "DUPLICATE_EMAIL"


def test_invalid_email_and_tier_are_rejected(client):
    response = client.post(
        "/api/members", json={"full_name": "X Y", "email": "nope", "tier": "VIP"}
    )
    assert response.status_code == 422


def test_list_filters_by_search_tier_and_status(client, make_member):
    make_member(full_name="Priya Nair", tier="STUDENT")
    make_member(full_name="Arjun Mehta", tier="FACULTY")
    inactive = make_member(full_name="Priya Kapoor", tier="STUDENT")
    client.put(f"/api/members/{inactive['id']}", json={"active": False})

    assert len(client.get("/api/members", params={"q": "priya"}).json()) == 2
    assert [m["full_name"] for m in client.get("/api/members?tier=FACULTY").json()] == [
        "Arjun Mehta"
    ]
    assert [m["full_name"] for m in client.get("/api/members?active=false").json()] == [
        "Priya Kapoor"
    ]


def test_update_member(client, make_member):
    member = make_member(tier="STUDENT")
    response = client.put(f"/api/members/{member['id']}", json={"tier": "FACULTY"})
    assert response.status_code == 200
    assert response.json()["tier"] == "FACULTY"


def test_get_unknown_member_is_404(client):
    assert client.get("/api/members/424242").status_code == 404


def test_delete_member_without_loans(client, make_member):
    member = make_member()
    assert client.delete(f"/api/members/{member['id']}").status_code == 204
    assert client.get(f"/api/members/{member['id']}").status_code == 404


def test_member_with_books_out_cannot_be_deleted(client, make_book, make_member, lend):
    member = make_member()
    lend(make_book(), member)
    response = client.delete(f"/api/members/{member['id']}")
    assert response.status_code == 409
    assert response.json()["code"] == "MEMBER_HAS_LOANS"


def test_account_shows_policy_loans_and_borrowing_status(client, make_book, make_member, lend):
    member = make_member(tier="PUBLIC")
    lend(make_book(title="Book A"), member)

    account = client.get(f"/api/members/{member['id']}/account").json()
    assert account["policy"]["max_active_loans"] == 3
    assert [loan["book_title"] for loan in account["active_loans"]] == ["Book A"]
    assert account["outstanding_fines"] == 0
    assert account["can_borrow"] is True
