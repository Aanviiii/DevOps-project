"""Database tables: the catalogue, library members, loans and the holds queue."""

import enum
from datetime import UTC, date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .core.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class MemberTier(enum.StrEnum):
    STUDENT = "STUDENT"
    FACULTY = "FACULTY"
    PUBLIC = "PUBLIC"


class HoldStatus(enum.StrEnum):
    WAITING = "WAITING"  # in the queue, no copy set aside yet
    READY = "READY"  # a copy is on the hold shelf for this member until ready_until
    FULFILLED = "FULFILLED"  # the member collected it (it became a loan)
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"  # the member never collected it in time


# Stored as VARCHAR + CHECK rather than a native Postgres ENUM, so adding a value later
# is a plain migration instead of an ALTER TYPE.
_tier = Enum(MemberTier, name="member_tier", native_enum=False, length=16)
_hold_status = Enum(HoldStatus, name="hold_status", native_enum=False, length=16)


class Book(Base):
    __tablename__ = "books"
    __table_args__ = (CheckConstraint("copies_total >= 0", name="copies_non_negative"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    isbn: Mapped[str] = mapped_column(String(17), unique=True)
    title: Mapped[str] = mapped_column(String(200), index=True)
    author: Mapped[str] = mapped_column(String(120), index=True)
    genre: Mapped[str] = mapped_column(String(40), index=True)
    published_year: Mapped[int | None] = mapped_column(Integer)
    copies_total: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    loans: Mapped[list["Loan"]] = relationship(back_populates="book", cascade="all, delete-orphan")
    holds: Mapped[list["Hold"]] = relationship(back_populates="book", cascade="all, delete-orphan")


class Member(Base):
    __tablename__ = "members"

    id: Mapped[int] = mapped_column(primary_key=True)
    card_number: Mapped[str] = mapped_column(String(12), unique=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(254), unique=True)
    tier: Mapped[MemberTier] = mapped_column(_tier, default=MemberTier.PUBLIC)
    active: Mapped[bool] = mapped_column(default=True)
    joined_on: Mapped[date] = mapped_column(Date, default=lambda: utcnow().date())

    loans: Mapped[list["Loan"]] = relationship(
        back_populates="member", cascade="all, delete-orphan"
    )
    holds: Mapped[list["Hold"]] = relationship(
        back_populates="member", cascade="all, delete-orphan"
    )


class Loan(Base):
    __tablename__ = "loans"
    __table_args__ = (
        CheckConstraint("due_on >= checked_out_on", name="due_after_checkout"),
        CheckConstraint("renewals >= 0", name="renewals_non_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), index=True)
    checked_out_on: Mapped[date] = mapped_column(Date)
    due_on: Mapped[date] = mapped_column(Date)
    returned_on: Mapped[date | None] = mapped_column(Date)
    renewals: Mapped[int] = mapped_column(Integer, default=0)

    book: Mapped[Book] = relationship(back_populates="loans")
    member: Mapped[Member] = relationship(back_populates="loans")


class Hold(Base):
    __tablename__ = "holds"

    id: Mapped[int] = mapped_column(primary_key=True)
    book_id: Mapped[int] = mapped_column(ForeignKey("books.id", ondelete="CASCADE"), index=True)
    member_id: Mapped[int] = mapped_column(ForeignKey("members.id", ondelete="CASCADE"), index=True)
    placed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    status: Mapped[HoldStatus] = mapped_column(_hold_status, default=HoldStatus.WAITING)
    ready_until: Mapped[date | None] = mapped_column(Date)

    book: Mapped[Book] = relationship(back_populates="holds")
    member: Mapped[Member] = relationship(back_populates="holds")
