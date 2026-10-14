from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..circulation import CirculationError
from ..core.database import get_db
from ..models import Book
from ..schemas import BookCreate, BookOut, BookUpdate
from ..services.catalogue import availability, book_out
from .common import get_or_404

router = APIRouter(prefix="/api/books", tags=["catalogue"])


@router.get("", response_model=list[BookOut])
def list_books(
    q: str | None = Query(default=None, max_length=100, description="Title, author or ISBN"),
    genre: str | None = Query(default=None, max_length=40),
    available_only: bool = False,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    query = select(Book).order_by(Book.title)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            or_(
                func.lower(Book.title).like(pattern),
                func.lower(Book.author).like(pattern),
                Book.isbn.like(f"%{q}%"),
            )
        )
    if genre:
        query = query.where(Book.genre == genre)

    books = db.scalars(query).all()
    stats = availability(db, [b.id for b in books])
    results = [book_out(b, stats.get(b.id)) for b in books]
    if available_only:
        results = [b for b in results if b.copies_available > 0]
    return results[offset : offset + limit]


@router.get("/genres", response_model=list[str])
def list_genres(db: Session = Depends(get_db)):
    return db.scalars(select(Book.genre).distinct().order_by(Book.genre)).all()


@router.get("/{book_id}", response_model=BookOut)
def get_book(book_id: int, db: Session = Depends(get_db)):
    book = get_or_404(db, Book, book_id)
    return book_out(book, availability(db, [book.id]).get(book.id))


@router.post("", response_model=BookOut, status_code=status.HTTP_201_CREATED)
def create_book(payload: BookCreate, db: Session = Depends(get_db)):
    book = Book(**payload.model_dump())
    db.add(book)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise CirculationError(
            "DUPLICATE_ISBN", f"ISBN {payload.isbn} is already catalogued."
        ) from exc
    return book_out(book, None)


@router.put("/{book_id}", response_model=BookOut)
def update_book(book_id: int, payload: BookUpdate, db: Session = Depends(get_db)):
    book = get_or_404(db, Book, book_id)
    stats = availability(db, [book.id]).get(book.id)
    changes = payload.model_dump(exclude_unset=True)

    on_loan = stats.on_loan if stats else 0
    if "copies_total" in changes and changes["copies_total"] < on_loan:
        raise CirculationError(
            "COPIES_ON_LOAN",
            f"{on_loan} copies are on loan; the total cannot drop below that.",
        )
    for field, value in changes.items():
        setattr(book, field, value)
    db.commit()
    return book_out(book, stats)


@router.delete("/{book_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_book(book_id: int, db: Session = Depends(get_db)):
    book = get_or_404(db, Book, book_id)
    stats = availability(db, [book.id]).get(book.id)
    if stats and stats.on_loan:
        raise CirculationError("BOOK_ON_LOAN", "Copies of this book are still on loan.")
    db.delete(book)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
