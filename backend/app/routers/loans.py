from datetime import date
from enum import StrEnum

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.clock import today as get_today
from ..core.database import get_db
from ..models import Loan
from ..schemas import LoanCreate, LoanOut
from ..services import circulation
from .common import get_or_404

router = APIRouter(prefix="/api/loans", tags=["circulation"])


class LoanFilter(StrEnum):
    ACTIVE = "active"
    OVERDUE = "overdue"
    RETURNED = "returned"
    ALL = "all"


@router.get("", response_model=list[LoanOut])
def list_loans(
    state: LoanFilter = LoanFilter.ACTIVE,
    member_id: int | None = None,
    book_id: int | None = None,
    db: Session = Depends(get_db),
    today: date = Depends(get_today),
):
    query = select(Loan).order_by(Loan.due_on, Loan.id)
    if state is LoanFilter.ACTIVE:
        query = query.where(Loan.returned_on.is_(None))
    elif state is LoanFilter.OVERDUE:
        query = query.where(Loan.returned_on.is_(None), Loan.due_on < today)
    elif state is LoanFilter.RETURNED:
        query = (
            query.where(Loan.returned_on.is_not(None))
            .order_by(None)
            .order_by(Loan.returned_on.desc(), Loan.id.desc())
        )
    if member_id is not None:
        query = query.where(Loan.member_id == member_id)
    if book_id is not None:
        query = query.where(Loan.book_id == book_id)
    return [circulation.loan_out(loan, today) for loan in db.scalars(query)]


@router.get("/{loan_id}", response_model=LoanOut)
def get_loan(loan_id: int, db: Session = Depends(get_db), today: date = Depends(get_today)):
    return circulation.loan_out(get_or_404(db, Loan, loan_id), today)


@router.post("", response_model=LoanOut, status_code=status.HTTP_201_CREATED)
def check_out(payload: LoanCreate, db: Session = Depends(get_db), today: date = Depends(get_today)):
    loan = circulation.checkout(
        db, book_id=payload.book_id, member_id=payload.member_id, today=today
    )
    return circulation.loan_out(loan, today)


@router.post("/{loan_id}/return", response_model=LoanOut)
def check_in(loan_id: int, db: Session = Depends(get_db), today: date = Depends(get_today)):
    loan = circulation.return_loan(db, loan=get_or_404(db, Loan, loan_id), today=today)
    return circulation.loan_out(loan, today)


@router.post("/{loan_id}/renew", response_model=LoanOut)
def renew(loan_id: int, db: Session = Depends(get_db), today: date = Depends(get_today)):
    loan = circulation.renew(db, loan=get_or_404(db, Loan, loan_id), today=today)
    return circulation.loan_out(loan, today)
