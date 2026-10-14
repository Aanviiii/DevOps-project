from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .circulation import CirculationError
from .core.config import get_settings
from .routers import books, holds, loans, members

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


@app.exception_handler(CirculationError)
def circulation_error(_: Request, exc: CirculationError) -> JSONResponse:
    # 409 Conflict: the request is well formed but clashes with the library's current state.
    # A missing book or member referenced in a request body is reported as 404.
    status_code = 404 if exc.code.endswith("_NOT_FOUND") else 409
    return JSONResponse(status_code=status_code, content={"code": exc.code, "detail": exc.message})


app.include_router(books.router)
app.include_router(members.router)
app.include_router(loans.router)
app.include_router(holds.router)
