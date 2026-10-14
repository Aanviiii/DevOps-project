"""create catalogue, members, loans and holds

Revision ID: 0001
Revises:
Create Date: 2026-10-15 01:21:28.036746
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "books",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("isbn", sa.String(length=17), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("author", sa.String(length=120), nullable=False),
        sa.Column("genre", sa.String(length=40), nullable=False),
        sa.Column("published_year", sa.Integer(), nullable=True),
        sa.Column("copies_total", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("copies_total >= 0", name=op.f("ck_books_copies_non_negative")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_books")),
        sa.UniqueConstraint("isbn", name=op.f("uq_books_isbn")),
    )
    op.create_index(op.f("ix_books_author"), "books", ["author"], unique=False)
    op.create_index(op.f("ix_books_genre"), "books", ["genre"], unique=False)
    op.create_index(op.f("ix_books_title"), "books", ["title"], unique=False)
    op.create_table(
        "members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("card_number", sa.String(length=12), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column(
            "tier",
            sa.Enum(
                "STUDENT", "FACULTY", "PUBLIC", name="member_tier", native_enum=False, length=16
            ),
            nullable=False,
        ),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("joined_on", sa.Date(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_members")),
        sa.UniqueConstraint("card_number", name=op.f("uq_members_card_number")),
        sa.UniqueConstraint("email", name=op.f("uq_members_email")),
    )
    op.create_table(
        "holds",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("placed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "WAITING",
                "READY",
                "FULFILLED",
                "CANCELLED",
                "EXPIRED",
                name="hold_status",
                native_enum=False,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("ready_until", sa.Date(), nullable=True),
        sa.ForeignKeyConstraint(
            ["book_id"], ["books.id"], name=op.f("fk_holds_book_id_books"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_holds_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_holds")),
    )
    op.create_index(op.f("ix_holds_book_id"), "holds", ["book_id"], unique=False)
    op.create_index(op.f("ix_holds_member_id"), "holds", ["member_id"], unique=False)
    op.create_table(
        "loans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("book_id", sa.Integer(), nullable=False),
        sa.Column("member_id", sa.Integer(), nullable=False),
        sa.Column("checked_out_on", sa.Date(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=False),
        sa.Column("returned_on", sa.Date(), nullable=True),
        sa.Column("renewals", sa.Integer(), nullable=False),
        sa.CheckConstraint("due_on >= checked_out_on", name=op.f("ck_loans_due_after_checkout")),
        sa.CheckConstraint("renewals >= 0", name=op.f("ck_loans_renewals_non_negative")),
        sa.ForeignKeyConstraint(
            ["book_id"], ["books.id"], name=op.f("fk_loans_book_id_books"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["member_id"],
            ["members.id"],
            name=op.f("fk_loans_member_id_members"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_loans")),
    )
    op.create_index(op.f("ix_loans_book_id"), "loans", ["book_id"], unique=False)
    op.create_index(op.f("ix_loans_member_id"), "loans", ["member_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_loans_member_id"), table_name="loans")
    op.drop_index(op.f("ix_loans_book_id"), table_name="loans")
    op.drop_table("loans")
    op.drop_index(op.f("ix_holds_member_id"), table_name="holds")
    op.drop_index(op.f("ix_holds_book_id"), table_name="holds")
    op.drop_table("holds")
    op.drop_table("members")
    op.drop_index(op.f("ix_books_title"), table_name="books")
    op.drop_index(op.f("ix_books_genre"), table_name="books")
    op.drop_index(op.f("ix_books_author"), table_name="books")
    op.drop_table("books")
