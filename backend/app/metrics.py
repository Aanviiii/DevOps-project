"""Library metrics for Prometheus, alongside the HTTP metrics from the instrumentator.

Two kinds:
- Counters for events (a checkout happened), incremented by the desk operations.
- Gauges for state (how many loans are overdue right now), computed from the database
  at scrape time by a custom collector, so every backend replica reports the same truth
  and nothing drifts after a restart.
"""

import logging
from datetime import UTC, datetime

from prometheus_client import REGISTRY, Counter, Info, disable_created_metrics
from prometheus_client.core import GaugeMetricFamily
from prometheus_client.registry import Collector
from sqlalchemy import func, select

from .circulation import fine_for, policy_for
from .core.database import SessionLocal
from .models import Hold, HoldStatus, Loan, Member

log = logging.getLogger(__name__)

# Skip the *_created timestamp series: they double the series count and nothing uses them.
disable_created_metrics()

CHECKOUTS = Counter("shelfwise_checkouts", "Books lent out", ["tier"])
RETURNS = Counter("shelfwise_returns", "Books returned", ["late"])
RENEWALS = Counter("shelfwise_renewals", "Loans renewed")
FINES_SETTLED = Counter("shelfwise_fines_settled_rupees", "Fines paid at the desk")
HOLDS_PLACED = Counter("shelfwise_holds_placed", "Holds placed on unavailable books")
REFUSALS = Counter("shelfwise_circulation_refusals", "Requests refused by a lending rule", ["code"])
BUILD = Info("shelfwise_build", "Version of the running backend")


class LibraryStateCollector(Collector):
    def describe(self):
        # Declaring the names up front stops the registry from calling collect() (and
        # so querying the database) at import time just to learn them.
        return [
            GaugeMetricFamily("shelfwise_overdue_loans", ""),
            GaugeMetricFamily("shelfwise_books_on_loan", ""),
            GaugeMetricFamily("shelfwise_outstanding_fines_rupees", ""),
            GaugeMetricFamily("shelfwise_hold_queue_depth", "", labels=["status"]),
        ]

    def collect(self):
        overdue = GaugeMetricFamily("shelfwise_overdue_loans", "Loans past their due date")
        on_loan = GaugeMetricFamily("shelfwise_books_on_loan", "Copies currently lent out")
        fines = GaugeMetricFamily(
            "shelfwise_outstanding_fines_rupees", "Unpaid fines, charged and still accruing"
        )
        queue = GaugeMetricFamily(
            "shelfwise_hold_queue_depth", "Open holds by status", labels=["status"]
        )
        try:
            today = datetime.now(UTC).date()
            with SessionLocal() as db:
                charged = db.scalar(
                    select(func.coalesce(func.sum(Loan.fine_charged), 0)).where(
                        Loan.returned_on.is_not(None), Loan.fine_settled_on.is_(None)
                    )
                )
                active = db.execute(
                    select(Loan.due_on, Member.tier)
                    .join(Member, Loan.member_id == Member.id)
                    .where(Loan.returned_on.is_(None))
                ).all()
                held = dict(
                    db.execute(
                        select(Hold.status, func.count())
                        .where(Hold.status.in_([HoldStatus.WAITING, HoldStatus.READY]))
                        .group_by(Hold.status)
                    ).all()
                )
        except Exception as exc:  # a scrape must never crash because the database blinked
            log.warning("library state metrics unavailable: %s", type(exc).__name__)
            return

        on_loan.add_metric([], len(active))
        overdue.add_metric([], sum(1 for due_on, _ in active if due_on < today))
        accruing = sum(fine_for(due_on, today, policy_for(tier)) for due_on, tier in active)
        fines.add_metric([], accruing + charged)
        for status in (HoldStatus.WAITING, HoldStatus.READY):
            queue.add_metric([status.value], held.get(status, 0))
        yield from (overdue, on_loan, fines, queue)


_registered = False


def register_library_collector(version: str) -> None:
    global _registered
    BUILD.info({"version": version})
    if not _registered:
        REGISTRY.register(LibraryStateCollector())
        _registered = True
