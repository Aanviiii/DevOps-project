from datetime import date

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..core.clock import today as get_today
from ..core.config import get_settings
from ..core.database import get_db
from ..schemas import LibraryStats
from ..services.stats import library_stats

router = APIRouter(tags=["system"])


@router.get("/")
def root():
    settings = get_settings()
    return {"service": settings.app_name, "version": settings.app_version, "docs": "/docs"}


@router.get("/health")
def health():
    """Liveness: the process is up and serving. Deliberately ignores the database, so a
    database outage does not make Kubernetes restart every healthy backend pod."""
    return {"status": "UP"}


@router.get("/ready")
def ready(response: Response, db: Session = Depends(get_db)):
    """Readiness: this pod can do useful work, which means reaching the database."""
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "NOT_READY", "database": "unreachable"}
    return {"status": "READY", "database": "ok"}


@router.get("/api/stats", response_model=LibraryStats, tags=["insights"])
def stats(db: Session = Depends(get_db), today: date = Depends(get_today)):
    return library_stats(db, today)
