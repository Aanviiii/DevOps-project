"""Numbers for the Insights dashboard."""

from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..circulation import fine_for, policy_for
from ..models import Book, Hold, HoldStatus, Loan, Member
from ..schemas import DailyCount, GenreCount, LibraryStats

TREND_DAYS = 14


def library_stats(db: Session, today: date) -> LibraryStats:
    active = db.execute(
        select(Loan.due_on, Member.tier)
        .join(Member, Loan.member_id == Member.id)
        .where(Loan.returned_on.is_(None))
    ).all()
    holds = dict(db.execute(select(Hold.status, func.count()).group_by(Hold.status)).all())

    since = today - timedelta(days=TREND_DAYS - 1)
    per_day = dict(
        db.execute(
            select(Loan.checked_out_on, func.count())
            .where(Loan.checked_out_on >= since)
            .group_by(Loan.checked_out_on)
        ).all()
    )
    genres = db.execute(
        select(Book.genre, func.count(Loan.id))
        .join(Loan, Loan.book_id == Book.id)
        .group_by(Book.genre)
        .order_by(func.count(Loan.id).desc(), Book.genre)
        .limit(5)
    ).all()

    unpaid = db.scalar(
        select(func.coalesce(func.sum(Loan.fine_charged), 0)).where(
            Loan.returned_on.is_not(None), Loan.fine_settled_on.is_(None)
        )
    )
    return LibraryStats(
        titles=db.scalar(select(func.count()).select_from(Book)) or 0,
        copies=db.scalar(select(func.coalesce(func.sum(Book.copies_total), 0))) or 0,
        members_active=db.scalar(select(func.count()).where(Member.active.is_(True))) or 0,
        on_loan=len(active),
        overdue=sum(1 for due_on, _ in active if due_on < today),
        outstanding_fines=unpaid
        + sum(fine_for(due, today, policy_for(tier)) for due, tier in active),
        holds_waiting=holds.get(HoldStatus.WAITING, 0),
        holds_ready=holds.get(HoldStatus.READY, 0),
        checkouts_by_day=[
            DailyCount(day=day, count=per_day.get(day, 0))
            for day in (since + timedelta(days=i) for i in range(TREND_DAYS))
        ],
        popular_genres=[GenreCount(genre=g, loans=n) for g, n in genres],
    )
