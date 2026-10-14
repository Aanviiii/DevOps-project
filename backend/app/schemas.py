"""Request and response bodies. Validation lives here so routers stay thin."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import HoldStatus, MemberTier

ISBN_PATTERN = r"^(97[89])?[0-9-]{9,14}[0-9Xx]$"


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------- books


class BookBase(BaseModel):
    title: str = Field(min_length=1, max_length=200, examples=["The Pragmatic Programmer"])
    author: str = Field(min_length=1, max_length=120, examples=["David Thomas"])
    genre: str = Field(min_length=1, max_length=40, examples=["Technology"])
    published_year: int | None = Field(default=None, ge=1450, le=2100)
    copies_total: int = Field(default=1, ge=0, le=500)


class BookCreate(BookBase):
    isbn: str = Field(pattern=ISBN_PATTERN, examples=["978-0135957059"])


class BookUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    author: str | None = Field(default=None, min_length=1, max_length=120)
    genre: str | None = Field(default=None, min_length=1, max_length=40)
    published_year: int | None = Field(default=None, ge=1450, le=2100)
    copies_total: int | None = Field(default=None, ge=0, le=500)


class BookOut(BookBase, ORMModel):
    id: int
    isbn: str
    created_at: datetime
    on_loan: int = 0
    copies_available: int = 0
    holds_waiting: int = 0


# ---------------------------------------------------------------- members


class MemberCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=120, examples=["Meera Iyer"])
    email: EmailStr
    tier: MemberTier = MemberTier.PUBLIC


class MemberUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    email: EmailStr | None = None
    tier: MemberTier | None = None
    active: bool | None = None


class MemberOut(ORMModel):
    id: int
    card_number: str
    full_name: str
    email: str
    tier: MemberTier
    active: bool
    joined_on: date


class PolicyOut(BaseModel):
    loan_days: int
    max_active_loans: int
    max_renewals: int
    fine_per_day: int
    grace_days: int
    fine_cap: int


# ---------------------------------------------------------------- loans and holds


class LoanOut(ORMModel):
    id: int
    book_id: int
    member_id: int
    book_title: str
    member_name: str
    checked_out_on: date
    due_on: date
    returned_on: date | None
    renewals: int
    days_overdue: int
    fine_due: int  # what this loan would cost if returned today (or what it cost)


class HoldOut(ORMModel):
    id: int
    book_id: int
    member_id: int
    book_title: str
    member_name: str
    placed_at: datetime
    status: HoldStatus
    ready_until: date | None
    queue_position: int | None


class MemberAccount(BaseModel):
    member: MemberOut
    policy: PolicyOut
    active_loans: list[LoanOut]
    holds: list[HoldOut]
    outstanding_fines: int
    can_borrow: bool


class ErrorOut(BaseModel):
    code: str
    detail: str
