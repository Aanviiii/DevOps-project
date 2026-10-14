from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from .circulation import CirculationError
from .core.config import get_settings
from .metrics import REFUSALS, register_library_collector
from .routers import books, holds, loans, members, system

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Catalogue, members, loans, fines and holds for a lending library.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def version_header(request: Request, call_next):
    # Lets anyone (or a smoke test after a deploy) see which commit served a response.
    response = await call_next(request)
    response.headers["X-Shelfwise-Version"] = settings.app_version
    return response


@app.exception_handler(CirculationError)
def circulation_error(_: Request, exc: CirculationError) -> JSONResponse:
    # 409 Conflict: the request is well formed but clashes with the library's current state.
    # A missing book or member referenced in a request body is reported as 404.
    status_code = 404 if exc.code.endswith("_NOT_FOUND") else 409
    REFUSALS.labels(code=exc.code).inc()
    return JSONResponse(status_code=status_code, content={"code": exc.code, "detail": exc.message})


app.include_router(system.router)
app.include_router(books.router)
app.include_router(members.router)
app.include_router(loans.router)
app.include_router(holds.router)

# HTTP request counts and latency histograms per route, plus the library's own metrics.
# Probe and scrape endpoints are excluded so they do not drown out real traffic.
Instrumentator(
    excluded_handlers=["/metrics", "/health", "/ready"],
    should_group_status_codes=False,
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
register_library_collector(settings.app_version)
