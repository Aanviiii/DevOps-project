"""Unit tests for the circulation engine. Every date is fixed, so no test depends on today."""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.circulation import (
    FINE_BLOCK_THRESHOLD,
    POLICIES,
    BorrowerState,
    CirculationError,
    LoanPolicy,
    QueueEntry,
    advance_queue,
    available_copies,
    check_checkout,
    days_overdue,
    due_date,
    fine_for,
    queue_position,
    renewed_due_date,
    shelf_copies,
)
from app.models import HoldStatus, MemberTier

pytestmark = pytest.mark.unit

STUDENT = POLICIES[MemberTier.STUDENT]
PUBLIC = POLICIES[MemberTier.PUBLIC]
OCT_1 = date(2026, 10, 1)


def at(day: int, hour: int = 9) -> datetime:
    return datetime(2026, 10, day, hour, tzinfo=UTC)


def borrower(**overrides) -> BorrowerState:
    values = dict(
        active=True,
        active_loans=0,
        outstanding_fines=0,
        already_has_this_book=False,
        has_ready_hold_for_this_book=False,
    )
    return BorrowerState(**(values | overrides))


# ---------------------------------------------------------------- policy table


def test_every_tier_has_a_policy():
    assert set(POLICIES) == set(MemberTier)


def test_faculty_borrow_longer_than_students():
    assert POLICIES[MemberTier.FACULTY].loan_days > STUDENT.loan_days


# ---------------------------------------------------------------- dates and fines


def test_due_date_adds_the_tier_loan_period():
    assert due_date(OCT_1, STUDENT) == date(2026, 10, 15)


@pytest.mark.parametrize(
    ("returned", "expected"),
    [(date(2026, 9, 30), 0), (OCT_1, 0), (date(2026, 10, 4), 3)],
)
def test_days_overdue_is_never_negative(returned, expected):
    assert days_overdue(OCT_1, returned) == expected


@pytest.mark.parametrize(
    ("days_late", "expected_fine"),
    [
        (0, 0),  # on time
        (1, 0),  # inside the one-day student grace period
        (2, 2),  # first chargeable day
        (9, 16),  # 8 chargeable days at 2 rupees
        (500, 100),  # capped
    ],
)
def test_student_fines_respect_grace_period_and_cap(days_late, expected_fine):
    assert fine_for(OCT_1, OCT_1 + timedelta(days=days_late), STUDENT) == expected_fine


def test_public_members_have_no_grace_period():
    assert fine_for(OCT_1, date(2026, 10, 2), PUBLIC) == PUBLIC.fine_per_day


def test_fine_cap_is_per_policy():
    generous = LoanPolicy(14, 3, 1, fine_per_day=50, grace_days=0, fine_cap=75)
    assert fine_for(OCT_1, date(2026, 10, 3), generous) == 75


# ---------------------------------------------------------------- availability


def test_shelf_copies_never_go_negative():
    assert shelf_copies(copies_total=2, active_loans=3) == 0


def test_ready_holds_take_copies_off_the_open_shelf():
    assert available_copies(copies_total=3, active_loans=1, ready_holds=1) == 1
    assert available_copies(copies_total=3, active_loans=1, ready_holds=5) == 0


# ---------------------------------------------------------------- checkout


def test_checkout_allowed_for_member_in_good_standing():
    check_checkout(borrower(), STUDENT, available=1)


@pytest.mark.parametrize(
    ("state", "available", "code"),
    [
        (dict(active=False), 1, "MEMBER_INACTIVE"),
        (dict(outstanding_fines=FINE_BLOCK_THRESHOLD), 1, "FINES_BLOCK"),
        (dict(active_loans=STUDENT.max_active_loans), 1, "LOAN_LIMIT"),
        (dict(already_has_this_book=True), 1, "DUPLICATE_LOAN"),
        (dict(), 0, "NOT_AVAILABLE"),
    ],
)
def test_checkout_refusals_carry_a_stable_code(state, available, code):
    with pytest.raises(CirculationError) as refused:
        check_checkout(borrower(**state), STUDENT, available=available)
    assert refused.value.code == code


def test_fines_just_under_the_threshold_do_not_block():
    check_checkout(borrower(outstanding_fines=FINE_BLOCK_THRESHOLD - 1), STUDENT, available=1)


def test_ready_hold_lets_member_borrow_the_copy_set_aside_for_them():
    check_checkout(borrower(has_ready_hold_for_this_book=True), STUDENT, available=0)


def test_inactive_member_is_refused_before_anything_else():
    state = borrower(active=False, outstanding_fines=999, active_loans=99)
    with pytest.raises(CirculationError) as refused:
        check_checkout(state, STUDENT, available=0)
    assert refused.value.code == "MEMBER_INACTIVE"


# ---------------------------------------------------------------- renewals


def test_renewal_restarts_loan_from_today_when_overdue():
    new_due = renewed_due_date(
        due_on=OCT_1, renewals=0, policy=STUDENT, today=date(2026, 10, 5), outstanding_fines=0
    )
    assert new_due == date(2026, 10, 19)


def test_early_renewal_never_shortens_the_loan():
    new_due = renewed_due_date(
        due_on=date(2026, 10, 20), renewals=0, policy=STUDENT, today=OCT_1, outstanding_fines=0
    )
    assert new_due == date(2026, 11, 3)


def test_renewal_limit_is_enforced():
    with pytest.raises(CirculationError) as refused:
        renewed_due_date(
            due_on=OCT_1,
            renewals=STUDENT.max_renewals,
            policy=STUDENT,
            today=OCT_1,
            outstanding_fines=0,
        )
    assert refused.value.code == "RENEWAL_LIMIT"


def test_fines_block_renewal():
    with pytest.raises(CirculationError) as refused:
        renewed_due_date(
            due_on=OCT_1, renewals=0, policy=STUDENT, today=OCT_1, outstanding_fines=500
        )
    assert refused.value.code == "FINES_BLOCK"


# ---------------------------------------------------------------- holds queue


def waiting(hold_id: int, day: int, hour: int = 9) -> QueueEntry:
    return QueueEntry(hold_id, at(day, hour), HoldStatus.WAITING, None)


def ready(hold_id: int, until: date) -> QueueEntry:
    return QueueEntry(hold_id, at(1), HoldStatus.READY, until)


def test_returned_copy_goes_to_the_earliest_waiting_hold():
    holds = [waiting(3, day=3), waiting(1, day=1), waiting(2, day=2)]
    changes = advance_queue(holds, shelf=1, today=date(2026, 10, 5))
    assert changes.readied == [1]
    assert changes.ready_until == date(2026, 10, 8)


def test_ties_on_placement_time_are_broken_by_hold_id():
    holds = [waiting(9, day=1), waiting(4, day=1)]
    assert advance_queue(holds, shelf=1, today=OCT_1).readied == [4]


def test_valid_ready_hold_keeps_its_copy():
    holds = [ready(1, until=date(2026, 10, 9)), waiting(2, day=2)]
    changes = advance_queue(holds, shelf=1, today=date(2026, 10, 5))
    assert changes.expired == []
    assert changes.readied == []


def test_lapsed_pickup_expires_and_passes_the_copy_on():
    holds = [ready(1, until=date(2026, 10, 4)), waiting(2, day=2)]
    changes = advance_queue(holds, shelf=1, today=date(2026, 10, 5))
    assert changes.expired == [1]
    assert changes.readied == [2]


def test_ready_hold_is_still_valid_on_its_last_day():
    holds = [ready(1, until=date(2026, 10, 5)), waiting(2, day=2)]
    assert advance_queue(holds, shelf=1, today=date(2026, 10, 5)).expired == []


def test_no_copies_in_the_building_means_nobody_is_readied():
    holds = [waiting(1, day=1)]
    assert advance_queue(holds, shelf=0, today=OCT_1).readied == []


def test_several_spare_copies_ready_several_holds():
    holds = [waiting(i, day=i) for i in range(1, 5)]
    assert advance_queue(holds, shelf=2, today=OCT_1).readied == [1, 2]


def test_queue_position_counts_only_waiting_holds():
    holds = [ready(1, until=OCT_1), waiting(2, day=1), waiting(3, day=2)]
    assert queue_position(holds, 3) == 2
    assert queue_position(holds, 1) is None


def test_renewal_is_refused_when_other_members_are_waiting():
    with pytest.raises(CirculationError) as refused:
        renewed_due_date(
            due_on=OCT_1,
            renewals=0,
            policy=STUDENT,
            today=OCT_1,
            outstanding_fines=0,
            others_waiting=True,
        )
    assert refused.value.code == "HELD_FOR_OTHERS"
