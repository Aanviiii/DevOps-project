"""Circulation desk operations: the database side of the pure rules in app.circulation."""

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..circulation import (
    BorrowerState,
    CirculationError,
    QueueEntry,
    advance_queue,
    available_copies,
    check_checkout,
    days_overdue,
    due_date,
    fine_for,
    policy_for,
    queue_position,
    renewed_due_date,
    shelf_copies,
)
from ..models import Book, Hold, HoldStatus, Loan, Member
from ..schemas import HoldOut, LoanOut
from .catalogue import availability

OPEN_HOLD = (HoldStatus.WAITING, HoldStatus.READY)


# ---------------------------------------------------------------- read helpers


def lock_book(db: Session, book_id: int) -> Book:
    """Load a book and lock its row until commit (Postgres), so two desks cannot lend the
    last copy at the same moment. SQLite simply ignores FOR UPDATE."""
    book = db.scalars(select(Book).where(Book.id == book_id).with_for_update()).first()
    if book is None:
        raise CirculationError("BOOK_NOT_FOUND", f"Book {book_id} does not exist.")
    return book


def require_member(db: Session, member_id: int) -> Member:
    member = db.get(Member, member_id)
    if member is None:
        raise CirculationError("MEMBER_NOT_FOUND", f"Member {member_id} does not exist.")
    return member


def active_loans(db: Session, member_id: int) -> list[Loan]:
    return list(
        db.scalars(
            select(Loan)
            .where(Loan.member_id == member_id, Loan.returned_on.is_(None))
            .order_by(Loan.due_on)
        )
    )


def outstanding_fines(db: Session, member: Member, today: date) -> int:
    """Fines accruing on the member's overdue books right now."""
    policy = policy_for(member.tier)
    return sum(fine_for(loan.due_on, today, policy) for loan in active_loans(db, member.id))


def copies_free(db: Session, book: Book) -> int:
    stats = availability(db, [book.id]).get(book.id)
    if stats is None:
        return book.copies_total
    return available_copies(book.copies_total, stats.on_loan, stats.ready_holds)


def queue_entries(holds: list[Hold]) -> list[QueueEntry]:
    return [QueueEntry(h.id, h.placed_at, h.status, h.ready_until) for h in holds]


def open_holds_for_book(db: Session, book_id: int) -> list[Hold]:
    return list(db.scalars(select(Hold).where(Hold.book_id == book_id, Hold.status.in_(OPEN_HOLD))))


# ---------------------------------------------------------------- holds queue


def refresh_queue(db: Session, book: Book, today: date) -> None:
    """Expire lapsed pickups and set copies aside for the next members in line."""
    holds = open_holds_for_book(db, book.id)
    if not holds:
        return
    on_loan = db.scalar(
        select(func.count())
        .select_from(Loan)
        .where(Loan.book_id == book.id, Loan.returned_on.is_(None))
    )
    changes = advance_queue(queue_entries(holds), shelf_copies(book.copies_total, on_loan), today)
    by_id = {h.id: h for h in holds}
    for hold_id in changes.expired:
        by_id[hold_id].status = HoldStatus.EXPIRED
    for hold_id in changes.readied:
        by_id[hold_id].status = HoldStatus.READY
        by_id[hold_id].ready_until = changes.ready_until
    db.flush()


def refresh_all_queues(db: Session, today: date) -> None:
    book_ids = db.scalars(select(Hold.book_id).where(Hold.status.in_(OPEN_HOLD)).distinct())
    for book_id in list(book_ids):
        refresh_queue(db, db.get(Book, book_id), today)


# ---------------------------------------------------------------- desk operations


def checkout(db: Session, *, book_id: int, member_id: int, today: date) -> Loan:
    book = lock_book(db, book_id)
    member = require_member(db, member_id)
    refresh_queue(db, book, today)

    loans = active_loans(db, member.id)
    my_hold = db.scalars(
        select(Hold).where(
            Hold.book_id == book.id, Hold.member_id == member.id, Hold.status.in_(OPEN_HOLD)
        )
    ).first()
    policy = policy_for(member.tier)
    check_checkout(
        BorrowerState(
            active=member.active,
            active_loans=len(loans),
            outstanding_fines=sum(fine_for(ln.due_on, today, policy) for ln in loans),
            already_has_this_book=any(ln.book_id == book.id for ln in loans),
            has_ready_hold_for_this_book=my_hold is not None and my_hold.status is HoldStatus.READY,
        ),
        policy,
        copies_free(db, book),
    )

    loan = Loan(
        book_id=book.id,
        member_id=member.id,
        checked_out_on=today,
        due_on=due_date(today, policy),
        renewals=0,
    )
    db.add(loan)
    if my_hold is not None:
        my_hold.status = HoldStatus.FULFILLED
    db.commit()
    return loan


def return_loan(db: Session, *, loan: Loan, today: date) -> Loan:
    if loan.returned_on is not None:
        raise CirculationError("ALREADY_RETURNED", f"Loan {loan.id} was returned already.")
    book = lock_book(db, loan.book_id)
    loan.returned_on = today
    db.flush()
    refresh_queue(db, book, today)
    db.commit()
    return loan


def renew(db: Session, *, loan: Loan, today: date) -> Loan:
    if loan.returned_on is not None:
        raise CirculationError("ALREADY_RETURNED", "A returned loan cannot be renewed.")
    member = loan.member
    loan.due_on = renewed_due_date(
        due_on=loan.due_on,
        renewals=loan.renewals,
        policy=policy_for(member.tier),
        today=today,
        outstanding_fines=outstanding_fines(db, member, today),
    )
    loan.renewals += 1
    db.commit()
    return loan


def place_hold(db: Session, *, book_id: int, member_id: int, today: date) -> Hold:
    book = lock_book(db, book_id)
    member = require_member(db, member_id)
    if not member.active:
        raise CirculationError("MEMBER_INACTIVE", "This membership is not active.")
    if any(ln.book_id == book.id for ln in active_loans(db, member.id)):
        raise CirculationError("ALREADY_BORROWED", "This member already has this book.")
    if any(h.member_id == member.id for h in open_holds_for_book(db, book.id)):
        raise CirculationError("DUPLICATE_HOLD", "This member is already in the queue.")

    refresh_queue(db, book, today)
    if copies_free(db, book) > 0:
        raise CirculationError("HOLD_NOT_NEEDED", "A copy is on the shelf; borrow it directly.")

    hold = Hold(book_id=book.id, member_id=member.id, status=HoldStatus.WAITING)
    db.add(hold)
    db.commit()
    return hold


def cancel_hold(db: Session, *, hold: Hold, today: date) -> Hold:
    if hold.status not in OPEN_HOLD:
        raise CirculationError("HOLD_CLOSED", f"This hold is already {hold.status.value}.")
    book = lock_book(db, hold.book_id)
    hold.status = HoldStatus.CANCELLED
    hold.ready_until = None
    db.flush()
    refresh_queue(db, book, today)
    db.commit()
    return hold


# ---------------------------------------------------------------- serialisation


def loan_out(loan: Loan, today: date) -> LoanOut:
    judged_on = loan.returned_on or today
    return LoanOut(
        id=loan.id,
        book_id=loan.book_id,
        member_id=loan.member_id,
        book_title=loan.book.title,
        member_name=loan.member.full_name,
        checked_out_on=loan.checked_out_on,
        due_on=loan.due_on,
        returned_on=loan.returned_on,
        renewals=loan.renewals,
        days_overdue=days_overdue(loan.due_on, judged_on),
        fine_due=fine_for(loan.due_on, judged_on, policy_for(loan.member.tier)),
    )


def hold_out(db: Session, hold: Hold) -> HoldOut:
    position = None
    if hold.status is HoldStatus.WAITING:
        position = queue_position(queue_entries(open_holds_for_book(db, hold.book_id)), hold.id)
    return HoldOut(
        id=hold.id,
        book_id=hold.book_id,
        member_id=hold.member_id,
        book_title=hold.book.title,
        member_name=hold.member.full_name,
        placed_at=hold.placed_at,
        status=hold.status,
        ready_until=hold.ready_until,
        queue_position=position,
    )
