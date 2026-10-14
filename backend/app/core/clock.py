from datetime import UTC, date, datetime


def today() -> date:
    """The library's current date. A FastAPI dependency, so tests can freeze time."""
    return datetime.now(UTC).date()
