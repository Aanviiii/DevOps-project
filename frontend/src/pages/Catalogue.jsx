import { useState } from "react";
import { api } from "../api";
import { BookPicker, MemberPicker } from "../components/Pickers";
import { Async, Badge, EmptyState, Field, Modal, useAction } from "../components/ui";
import { coverHue, initials, plural } from "../format";
import { useDebounced, useLoad } from "../hooks";

const EMPTY_BOOK = {
  isbn: "",
  title: "",
  author: "",
  genre: "",
  published_year: "",
  copies_total: 1,
};

function Cover({ book }) {
  const hue = coverHue(book.title);
  return (
    <div className="cover" style={{ "--hue": hue }} aria-hidden="true">
      <span className="cover-initials">{initials(book.title)}</span>
      <span className="cover-author">{book.author}</span>
    </div>
  );
}

function Availability({ book }) {
  if (book.copies_available > 0) {
    return (
      <Badge tone="green">
        {book.copies_available} of {book.copies_total} on shelf
      </Badge>
    );
  }
  if (book.copies_total === 0) return <Badge>Withdrawn</Badge>;
  return (
    <Badge tone="amber">
      All out{book.holds_waiting > 0 ? ` · ${plural(book.holds_waiting, "hold")}` : ""}
    </Badge>
  );
}

function BookForm({ initial, onSubmit, onCancel, isNew }) {
  const [book, setBook] = useState(initial);
  const set = (key) => (e) => setBook({ ...book, [key]: e.target.value });

  const submit = (event) => {
    event.preventDefault();
    const body = {
      ...book,
      published_year: book.published_year === "" ? null : Number(book.published_year),
      copies_total: Number(book.copies_total),
    };
    if (!isNew) delete body.isbn;
    onSubmit(body);
  };

  return (
    <form className="form" onSubmit={submit}>
      <Field label="Title">
        <input required maxLength={200} value={book.title} onChange={set("title")} />
      </Field>
      <div className="form-row">
        <Field label="Author">
          <input required maxLength={120} value={book.author} onChange={set("author")} />
        </Field>
        <Field label="Genre">
          <input required maxLength={40} value={book.genre} onChange={set("genre")} />
        </Field>
      </div>
      <div className="form-row">
        <Field label="ISBN" hint={isNew ? "10 or 13 digits, hyphens allowed" : "Fixed once catalogued"}>
          <input required disabled={!isNew} value={book.isbn} onChange={set("isbn")} />
        </Field>
        <Field label="Year">
          <input type="number" min="1450" max="2100" value={book.published_year ?? ""} onChange={set("published_year")} />
        </Field>
        <Field label="Copies">
          <input type="number" min="0" max="500" required value={book.copies_total} onChange={set("copies_total")} />
        </Field>
      </div>
      <div className="form-actions">
        <button type="button" className="button button-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button className="button">{isNew ? "Add to catalogue" : "Save changes"}</button>
      </div>
    </form>
  );
}

// Lend a specific book, or place a hold on it when no copy is free.
function LendDialog({ book, mode, onDone, onCancel }) {
  const [member, setMember] = useState(null);
  const [chosenBook, setChosenBook] = useState(book);
  const act = useAction();
  const isHold = mode === "hold";

  const submit = async (event) => {
    event.preventDefault();
    const ok = isHold
      ? await act(
          () => api.holds.place(chosenBook.id, member.id),
          (h) => `${member.full_name} is #${h.queue_position} in the queue for “${chosenBook.title}”.`,
        )
      : await act(
          () => api.loans.checkout(chosenBook.id, member.id),
          (loan) => `Lent “${loan.book_title}” to ${loan.member_name}.`,
        );
    if (ok) onDone();
  };

  return (
    <form className="form" onSubmit={submit}>
      {!book && (
        <Field label="Book">
          <BookPicker value={chosenBook} onChange={setChosenBook} />
        </Field>
      )}
      {book && (
        <p className="dialog-lead">
          <strong>{book.title}</strong> by {book.author}
        </p>
      )}
      <Field label="Member">
        <MemberPicker value={member} onChange={setMember} />
      </Field>
      <div className="form-actions">
        <button type="button" className="button button-secondary" onClick={onCancel}>
          Cancel
        </button>
        <button className="button" disabled={!member || !chosenBook}>
          {isHold ? "Place hold" : "Lend book"}
        </button>
      </div>
    </form>
  );
}

export default function Catalogue() {
  const [query, setQuery] = useState("");
  const [genre, setGenre] = useState("");
  const [availableOnly, setAvailableOnly] = useState(false);
  const [dialog, setDialog] = useState(null);
  const q = useDebounced(query);
  const act = useAction();

  const books = useLoad(
    () => api.books.list({ q, genre, available_only: availableOnly || undefined }),
    [q, genre, availableOnly],
  );
  const genres = useLoad(() => api.books.genres(), []);

  const close = () => setDialog(null);
  const closeAndReload = () => {
    setDialog(null);
    books.reload();
    genres.reload();
  };

  const save = async (body) => {
    const isNew = dialog.type === "new";
    const ok = await act(
      () => (isNew ? api.books.create(body) : api.books.update(dialog.book.id, body)),
      (b) => (isNew ? `Added “${b.title}” to the catalogue.` : `Saved “${b.title}”.`),
    );
    if (ok) closeAndReload();
  };

  const remove = async (book) => {
    if (!window.confirm(`Remove “${book.title}” from the catalogue?`)) return;
    if (await act(() => api.books.remove(book.id), () => `Removed “${book.title}”.`)) {
      books.reload();
      genres.reload();
    }
  };

  return (
    <>
      <div className="toolbar">
        <input
          type="search"
          className="search"
          placeholder="Search title, author or ISBN"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="Search the catalogue"
        />
        <label className="toggle">
          <input
            type="checkbox"
            checked={availableOnly}
            onChange={(e) => setAvailableOnly(e.target.checked)}
          />
          On shelf only
        </label>
        <button className="button" onClick={() => setDialog({ type: "new" })}>
          + Add book
        </button>
      </div>

      <div className="chips" role="group" aria-label="Filter by genre">
        <button className={`chip ${genre === "" ? "is-active" : ""}`} onClick={() => setGenre("")}>
          All genres
        </button>
        {genres.data?.map((g) => (
          <button key={g} className={`chip ${genre === g ? "is-active" : ""}`} onClick={() => setGenre(g)}>
            {g}
          </button>
        ))}
      </div>

      <Async
        result={books}
        empty={
          <EmptyState title="No books match">
            Try another search, or add the first title to the catalogue.
          </EmptyState>
        }
      >
        {(list) => (
          <div className="book-grid">
            {list.map((book) => (
              <article className="book-card" key={book.id}>
                <Cover book={book} />
                <div className="book-body">
                  <h3>{book.title}</h3>
                  <p className="muted">
                    {book.author}
                    {book.published_year ? ` · ${book.published_year}` : ""}
                  </p>
                  <div className="book-meta">
                    <Badge tone="ink">{book.genre}</Badge>
                    <Availability book={book} />
                  </div>
                  <div className="card-actions">
                    {book.copies_available > 0 ? (
                      <button className="button button-small" onClick={() => setDialog({ type: "lend", book })}>
                        Lend
                      </button>
                    ) : (
                      book.copies_total > 0 && (
                        <button
                          className="button button-small button-amber"
                          onClick={() => setDialog({ type: "hold", book })}
                        >
                          Place hold
                        </button>
                      )
                    )}
                    <button
                      className="button button-small button-ghost"
                      onClick={() => setDialog({ type: "edit", book })}
                    >
                      Edit
                    </button>
                    <button className="button button-small button-ghost danger" onClick={() => remove(book)}>
                      Remove
                    </button>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}
      </Async>

      {(dialog?.type === "new" || dialog?.type === "edit") && (
        <Modal title={dialog.type === "new" ? "Add a book" : `Edit “${dialog.book.title}”`} onClose={close}>
          <BookForm
            isNew={dialog.type === "new"}
            initial={dialog.book ?? EMPTY_BOOK}
            onSubmit={save}
            onCancel={close}
          />
        </Modal>
      )}
      {(dialog?.type === "lend" || dialog?.type === "hold") && (
        <Modal title={dialog.type === "lend" ? "Lend this book" : "Join the holds queue"} onClose={close}>
          <LendDialog book={dialog.book} mode={dialog.type} onDone={closeAndReload} onCancel={close} />
        </Modal>
      )}
    </>
  );
}

export { LendDialog };
