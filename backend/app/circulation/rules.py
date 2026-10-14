"""Circulation rules as pure functions.

Nothing here touches the database or reads the clock: every function receives `today`
and plain values. That keeps the rules easy to reason about and lets the tests pin any
date they like without mocking.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from ..models import HoldStatus
from .policy import FINE_BLOCK_THRESHOLD, HOLD_PICKUP_DAYS, LoanPolicy


class CirculationError(Exception):
    """A request that breaks a lending rule. `code` is stable and machine-readable."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# ---------------------------------------------------------------- dates and fines


def due_date(start: date, policy: LoanPolicy) -> date:
    return start + timedelta(days=policy.loan_days)


def days_overdue(due_on: date, on: date) -> int:
    return max(0, (on - due_on).days)


def fine_for(due_on: date, on: date, policy: LoanPolicy) -> int:
    """Fine in rupees for a loan due on `due_on`, judged on `on` (return day or today).

    The grace period is forgiven outright; every later day costs `fine_per_day`, and the
    total never exceeds the per-loan cap.
    """
    chargeable_days = days_overdue(due_on, on) - policy.grace_days
    if chargeable_days <= 0:
        return 0
    return min(chargeable_days * policy.fine_per_day, policy.fine_cap)


# ---------------------------------------------------------------- availability


def shelf_copies(copies_total: int, active_loans: int) -> int:
    """Copies physically in the library (on the open shelf or the hold shelf)."""
    return max(0, copies_total - active_loans)


def available_copies(copies_total: int, active_loans: int, ready_holds: int) -> int:
    """Copies anyone may walk up and borrow: in the building and not set aside for a hold."""
    return max(0, shelf_copies(copies_total, active_loans) - ready_holds)


# ---------------------------------------------------------------- checkout / renew


@dataclass(frozen=True)
class BorrowerState:
    """What the rules need to know about a member at the moment they try to borrow."""

    active: bool
    active_loans: int
    outstanding_fines: int
    already_has_this_book: bool
    has_ready_hold_for_this_book: bool


def check_checkout(borrower: BorrowerState, policy: LoanPolicy, available: int) -> None:
    """Raise CirculationError if this checkout is not allowed; return None if it is.

    Checks run in the order a librarian would explain them, so the member hears about
    the most fundamental problem first.
    """
    if not borrower.active:
        raise CirculationError("MEMBER_INACTIVE", "This membership is not active.")
    if borrower.outstanding_fines >= FINE_BLOCK_THRESHOLD:
        raise CirculationError(
            "FINES_BLOCK",
            f"Outstanding fines of ₹{borrower.outstanding_fines} must be settled first "
            f"(limit ₹{FINE_BLOCK_THRESHOLD}).",
        )
    if borrower.active_loans >= policy.max_active_loans:
        raise CirculationError(
            "LOAN_LIMIT", f"Loan limit reached ({policy.max_active_loans} books at a time)."
        )
    if borrower.already_has_this_book:
        raise CirculationError("DUPLICATE_LOAN", "This member already has a copy of this book.")
    # A member whose hold is READY borrows the copy set aside for them, even when the
    # open shelf is empty.
    if not borrower.has_ready_hold_for_this_book and available <= 0:
        raise CirculationError(
            "NOT_AVAILABLE", "No copies are available. Place a hold to join the queue."
        )


def renewed_due_date(
    *,
    due_on: date,
    renewals: int,
    policy: LoanPolicy,
    today: date,
    outstanding_fines: int,
) -> date:
    """Return the new due date for a renewal, or raise CirculationError.

    A renewal restarts the loan period from today (or from the current due date if the
    member renews early), so renewing early never shortens a loan.
    """
    if renewals >= policy.max_renewals:
        raise CirculationError(
            "RENEWAL_LIMIT", f"This loan has used all {policy.max_renewals} renewals."
        )
    if outstanding_fines >= FINE_BLOCK_THRESHOLD:
        raise CirculationError("FINES_BLOCK", "Outstanding fines must be settled before renewing.")
    return due_date(max(due_on, today), policy)


# ---------------------------------------------------------------- holds queue


@dataclass(frozen=True)
class QueueEntry:
    hold_id: int
    placed_at: datetime
    status: HoldStatus
    ready_until: date | None


@dataclass(frozen=True)
class QueueChanges:
    expired: list[int]  # READY holds whose pickup window has passed
    readied: list[int]  # WAITING holds that now have a copy set aside
    ready_until: date  # pickup deadline for every newly readied hold


def advance_queue(holds: Sequence[QueueEntry], shelf: int, today: date) -> QueueChanges:
    """Work out how a book's holds queue moves on `today`.

    `shelf` is the number of copies in the building. Each still-valid READY hold keeps
    the copy set aside for it; lapsed READY holds expire and give their copy back; any
    spare copies go to WAITING holds strictly first-come, first-served.
    """
    ready = [h for h in holds if h.status is HoldStatus.READY]
    expired = [h.hold_id for h in ready if h.ready_until is not None and h.ready_until < today]
    still_ready = len(ready) - len(expired)

    spare = max(0, shelf - still_ready)
    waiting = sorted(
        (h for h in holds if h.status is HoldStatus.WAITING),
        key=lambda h: (h.placed_at, h.hold_id),
    )
    readied = [h.hold_id for h in waiting[:spare]]

    return QueueChanges(
        expired=expired,
        readied=readied,
        ready_until=today + timedelta(days=HOLD_PICKUP_DAYS),
    )


def queue_position(holds: Sequence[QueueEntry], hold_id: int) -> int | None:
    """1-based place of a WAITING hold in its queue, or None if it is not waiting."""
    waiting = sorted(
        (h for h in holds if h.status is HoldStatus.WAITING),
        key=lambda h: (h.placed_at, h.hold_id),
    )
    for position, entry in enumerate(waiting, start=1):
        if entry.hold_id == hold_id:
            return position
    return None
