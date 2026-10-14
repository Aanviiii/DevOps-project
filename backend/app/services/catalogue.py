"""Catalogue queries: how many copies of each book are out, set aside or free."""

from collections.abc import Iterable
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..circulation import available_copies
from ..models import Book, Hold, HoldStatus, Loan
from ..schemas import BookOut


@dataclass(frozen=True)
class Availability:
    on_loan: int = 0
    ready_holds: int = 0
    waiting_holds: int = 0


def availability(db: Session, book_ids: Iterable[int] | None = None) -> dict[int, Availability]:
    """Loan and hold counts per book, in two grouped queries rather than one per book."""
    loans = select(Loan.book_id, func.count()).where(Loan.returned_on.is_(None))
    holds = select(Hold.book_id, Hold.status, func.count()).where(
        Hold.status.in_([HoldStatus.READY, HoldStatus.WAITING])
    )
    if book_ids is not None:
        ids = list(book_ids)
        loans = loans.where(Loan.book_id.in_(ids))
        holds = holds.where(Hold.book_id.in_(ids))

    on_loan = dict(db.execute(loans.group_by(Loan.book_id)).all())
    counts: dict[int, dict[HoldStatus, int]] = {}
    for book_id, status, count in db.execute(holds.group_by(Hold.book_id, Hold.status)):
        counts.setdefault(book_id, {})[status] = count

    result = {}
    for book_id in set(on_loan) | set(counts):
        by_status = counts.get(book_id, {})
        result[book_id] = Availability(
            on_loan=on_loan.get(book_id, 0),
            ready_holds=by_status.get(HoldStatus.READY, 0),
            waiting_holds=by_status.get(HoldStatus.WAITING, 0),
        )
    return result


def book_out(book: Book, stats: Availability | None) -> BookOut:
    stats = stats or Availability()
    return BookOut.model_validate(book).model_copy(
        update={
            "on_loan": stats.on_loan,
            "copies_available": available_copies(
                book.copies_total, stats.on_loan, stats.ready_holds
            ),
            "holds_waiting": stats.waiting_holds,
        }
    )
