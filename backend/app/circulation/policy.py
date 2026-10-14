"""Lending rules for each membership tier.

Kept as plain data so the rules a librarian would recognise ("students get 14 days, two
renewals") live in one place instead of being scattered through the API code.
"""

from dataclasses import dataclass

from ..models import MemberTier


@dataclass(frozen=True)
class LoanPolicy:
    loan_days: int  # length of a loan and of each renewal
    max_active_loans: int  # books a member may hold at once
    max_renewals: int  # renewals allowed per loan
    fine_per_day: int  # rupees per day overdue, once the grace period is used up
    grace_days: int  # days overdue that are forgiven
    fine_cap: int  # the most one loan can ever be fined


POLICIES: dict[MemberTier, LoanPolicy] = {
    MemberTier.STUDENT: LoanPolicy(
        loan_days=14, max_active_loans=5, max_renewals=2, fine_per_day=2, grace_days=1, fine_cap=100
    ),
    MemberTier.FACULTY: LoanPolicy(
        loan_days=28,
        max_active_loans=10,
        max_renewals=3,
        fine_per_day=1,
        grace_days=3,
        fine_cap=100,
    ),
    MemberTier.PUBLIC: LoanPolicy(
        loan_days=14, max_active_loans=3, max_renewals=1, fine_per_day=5, grace_days=0, fine_cap=200
    ),
}

# Members owing this much (in rupees) cannot borrow or renew until they settle up.
FINE_BLOCK_THRESHOLD = 150

# Days a READY hold waits on the hold shelf before it lapses to the next member in line.
HOLD_PICKUP_DAYS = 3


def policy_for(tier: MemberTier) -> LoanPolicy:
    return POLICIES[tier]
