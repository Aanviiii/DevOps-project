def test_create_book_returns_it_with_availability(client):
    response = client.post(
        "/api/books",
        json={
            "isbn": "978-0135957059",
            "title": "The Pragmatic Programmer",
            "author": "David Thomas",
            "genre": "Technology",
            "copies_total": 3,
        },
    )
    assert response.status_code == 201
    book = response.json()
    assert book["id"] > 0
    assert book["copies_available"] == 3
    assert book["on_loan"] == 0


def test_duplicate_isbn_is_a_conflict(client, make_book):
    book = make_book()
    response = client.post(
        "/api/books",
        json={"isbn": book["isbn"], "title": "Copy", "author": "Someone", "genre": "Misc"},
    )
    assert response.status_code == 409
    assert response.json()["code"] == "DUPLICATE_ISBN"


def test_invalid_book_is_rejected_by_validation(client):
    response = client.post(
        "/api/books",
        json={"isbn": "not-an-isbn", "title": "", "author": "A", "genre": "B", "copies_total": -1},
    )
    assert response.status_code == 422
    fields = {error["loc"][-1] for error in response.json()["detail"]}
    assert {"isbn", "title", "copies_total"} <= fields


def test_list_searches_title_author_and_isbn(client, make_book):
    make_book(title="Clean Code", author="Robert Martin")
    make_book(title="Refactoring", author="Martin Fowler")
    make_book(title="Dune", author="Frank Herbert", genre="Fiction")

    titles = [b["title"] for b in client.get("/api/books", params={"q": "martin"}).json()]
    assert titles == ["Clean Code", "Refactoring"]  # sorted by title


def test_list_filters_by_genre_and_lists_genres(client, make_book):
    make_book(genre="Fiction", title="Dune")
    make_book(genre="History", title="Sapiens")

    fiction = client.get("/api/books", params={"genre": "Fiction"}).json()
    assert [b["title"] for b in fiction] == ["Dune"]
    assert client.get("/api/books/genres").json() == ["Fiction", "History"]


def test_available_only_hides_books_that_are_all_out(client, make_book, make_member, lend):
    out = make_book(title="All Out")
    make_book(title="On Shelf")
    lend(out, make_member())

    titles = [b["title"] for b in client.get("/api/books?available_only=true").json()]
    assert titles == ["On Shelf"]


def test_get_unknown_book_is_404(client):
    assert client.get("/api/books/9999").status_code == 404


def test_update_book_changes_only_sent_fields(client, make_book):
    book = make_book(title="Old Title")
    response = client.put(f"/api/books/{book['id']}", json={"title": "New Title"})
    assert response.status_code == 200
    assert response.json()["title"] == "New Title"
    assert response.json()["author"] == book["author"]


def test_copies_cannot_drop_below_those_on_loan(client, make_book, make_member, lend):
    book = make_book(copies_total=2)
    lend(book, make_member())
    lend(book, make_member())

    response = client.put(f"/api/books/{book['id']}", json={"copies_total": 1})
    assert response.status_code == 409
    assert response.json()["code"] == "COPIES_ON_LOAN"


def test_delete_book(client, make_book):
    book = make_book()
    assert client.delete(f"/api/books/{book['id']}").status_code == 204
    assert client.get(f"/api/books/{book['id']}").status_code == 404


def test_book_on_loan_cannot_be_deleted(client, make_book, make_member, lend):
    book = make_book()
    lend(book, make_member())
    response = client.delete(f"/api/books/{book['id']}")
    assert response.status_code == 409
    assert response.json()["code"] == "BOOK_ON_LOAN"
