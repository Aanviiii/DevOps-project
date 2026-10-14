"""record fines on return and index open loans by due date

Fines used to exist only while a book was out: once returned, a late book's fine was
forgotten. Loans now keep the fine charged at return and the date it was settled.

Existing rows get fine_charged = 0 through the server default, so the migration is
safe on a live table and needs no backfill: loans returned before it are treated as
settled history.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # batch_alter_table rebuilds the table on SQLite (which cannot add constraints in
    # place) and issues plain ALTER TABLE statements on Postgres.
    with op.batch_alter_table("loans") as batch:
        batch.add_column(
            sa.Column("fine_charged", sa.Integer(), server_default="0", nullable=False)
        )
        batch.add_column(sa.Column("fine_settled_on", sa.Date(), nullable=True))
        batch.create_check_constraint("fine_non_negative", "fine_charged >= 0")
    op.create_index("ix_loans_open_by_due", "loans", ["returned_on", "due_on"])


def downgrade() -> None:
    op.drop_index("ix_loans_open_by_due", table_name="loans")
    with op.batch_alter_table("loans") as batch:
        batch.drop_constraint("fine_non_negative", type_="check")
        batch.drop_column("fine_settled_on")
        batch.drop_column("fine_charged")
