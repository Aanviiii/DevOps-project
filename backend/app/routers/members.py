from uuid import uuid4

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..circulation import CirculationError
from ..core.database import get_db
from ..models import Loan, Member, MemberTier
from ..schemas import MemberCreate, MemberOut, MemberUpdate
from .common import get_or_404

router = APIRouter(prefix="/api/members", tags=["members"])


def card_number_for(member_id: int) -> str:
    """Library card numbers are derived from the row id: SW-000042."""
    return f"SW-{member_id:06d}"


def _duplicate_email(email: str) -> CirculationError:
    return CirculationError("DUPLICATE_EMAIL", f"{email} already belongs to a member.")


@router.get("", response_model=list[MemberOut])
def list_members(
    q: str | None = Query(default=None, max_length=100, description="Name, email or card"),
    tier: MemberTier | None = None,
    active: bool | None = None,
    db: Session = Depends(get_db),
):
    query = select(Member).order_by(Member.full_name)
    if q:
        pattern = f"%{q.lower()}%"
        query = query.where(
            or_(
                func.lower(Member.full_name).like(pattern),
                func.lower(Member.email).like(pattern),
                func.lower(Member.card_number).like(pattern),
            )
        )
    if tier:
        query = query.where(Member.tier == tier)
    if active is not None:
        query = query.where(Member.active.is_(active))
    return db.scalars(query).all()


@router.get("/{member_id}", response_model=MemberOut)
def get_member(member_id: int, db: Session = Depends(get_db)):
    return get_or_404(db, Member, member_id)


@router.post("", response_model=MemberOut, status_code=status.HTTP_201_CREATED)
def create_member(payload: MemberCreate, db: Session = Depends(get_db)):
    # Insert with a unique placeholder, then derive the real card number from the new id.
    member = Member(**payload.model_dump(), card_number=uuid4().hex[:12])
    db.add(member)
    try:
        db.flush()
        member.card_number = card_number_for(member.id)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_email(payload.email) from exc
    return member


@router.put("/{member_id}", response_model=MemberOut)
def update_member(member_id: int, payload: MemberUpdate, db: Session = Depends(get_db)):
    member = get_or_404(db, Member, member_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(member, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _duplicate_email(str(payload.email)) from exc
    return member


@router.delete("/{member_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_member(member_id: int, db: Session = Depends(get_db)):
    member = get_or_404(db, Member, member_id)
    open_loans = db.scalar(
        select(func.count())
        .select_from(Loan)
        .where(Loan.member_id == member.id, Loan.returned_on.is_(None))
    )
    if open_loans:
        raise CirculationError(
            "MEMBER_HAS_LOANS", f"This member still has {open_loans} book(s) to return."
        )
    db.delete(member)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
