from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..core.clock import today as get_today
from ..core.database import get_db
from ..models import Hold, HoldStatus
from ..schemas import HoldCreate, HoldOut
from ..services import circulation
from .common import get_or_404

router = APIRouter(prefix="/api/holds", tags=["circulation"])


@router.get("", response_model=list[HoldOut])
def list_holds(
    hold_status: HoldStatus | None = Query(default=None, alias="status"),
    book_id: int | None = None,
    member_id: int | None = None,
    db: Session = Depends(get_db),
    today: date = Depends(get_today),
):
    # Pickup windows lapse with the calendar, not with requests, so bring every queue up
    # to date before reporting on it.
    circulation.refresh_all_queues(db, today)
    db.commit()

    query = select(Hold).order_by(Hold.placed_at, Hold.id)
    if hold_status is not None:
        query = query.where(Hold.status == hold_status)
    else:
        query = query.where(Hold.status.in_(circulation.OPEN_HOLD))
    if book_id is not None:
        query = query.where(Hold.book_id == book_id)
    if member_id is not None:
        query = query.where(Hold.member_id == member_id)
    return [circulation.hold_out(db, hold) for hold in db.scalars(query)]


@router.post("", response_model=HoldOut, status_code=status.HTTP_201_CREATED)
def place_hold(
    payload: HoldCreate, db: Session = Depends(get_db), today: date = Depends(get_today)
):
    hold = circulation.place_hold(
        db, book_id=payload.book_id, member_id=payload.member_id, today=today
    )
    return circulation.hold_out(db, hold)


@router.post("/{hold_id}/cancel", response_model=HoldOut)
def cancel_hold(hold_id: int, db: Session = Depends(get_db), today: date = Depends(get_today)):
    hold = circulation.cancel_hold(db, hold=get_or_404(db, Hold, hold_id), today=today)
    return circulation.hold_out(db, hold)
