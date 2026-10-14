"""Fill an empty database with a believable month of library activity.

    python -m app.seed

Runs the real circulation rules day by day over the last few weeks (checkouts, returns,
renewals, late books and holds), so the dashboards have history to show. A fixed random
seed makes the result the same every time. Does nothing if books already exist.
"""

import random
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import func, select

from .circulation import CirculationError
from .core.clock import today
from .core.database import SessionLocal
from .models import Book, Hold, HoldStatus, Loan, Member, MemberTier
from .routers.members import card_number_for
from .services import circulation

BOOKS = [
    ("978-0-13-595705-9", "The Pragmatic Programmer", "David Thomas", "Technology", 2019, 3),
    ("978-0-13-235088-4", "Clean Code", "Robert C. Martin", "Technology", 2008, 2),
    (
        "978-1-4919-5016-0",
        "Designing Data-Intensive Applications",
        "Martin Kleppmann",
        "Technology",
        2017,
        2,
    ),
    ("978-1-4920-4034-7", "Kubernetes Up and Running", "Brendan Burns", "Technology", 2019, 1),
    (
        "978-0-262-03384-8",
        "Introduction to Algorithms",
        "Thomas H. Cormen",
        "Computer Science",
        2009,
        2,
    ),
    (
        "978-0-13-110362-7",
        "The C Programming Language",
        "Brian Kernighan",
        "Computer Science",
        1988,
        1,
    ),
    ("978-0-14-303943-3", "The God of Small Things", "Arundhati Roy", "Fiction", 1997, 2),
    ("978-0-09-957807-3", "Midnight's Children", "Salman Rushdie", "Fiction", 1981, 1),
    ("978-0-06-231609-7", "The Alchemist", "Paulo Coelho", "Fiction", 1988, 3),
    ("978-0-7432-7356-5", "The Great Gatsby", "F. Scott Fitzgerald", "Fiction", 1925, 2),
    ("978-0-441-17271-9", "Dune", "Frank Herbert", "Science Fiction", 1965, 2),
    ("978-0-553-29335-7", "Foundation", "Isaac Asimov", "Science Fiction", 1951, 1),
    (
        "978-0-345-39180-3",
        "The Hitchhiker's Guide to the Galaxy",
        "Douglas Adams",
        "Science Fiction",
        1979,
        2,
    ),
    ("978-0-06-231609-8", "Sapiens", "Yuval Noah Harari", "History", 2011, 3),
    ("978-0-14-303467-4", "India After Gandhi", "Ramachandra Guha", "History", 2007, 1),
    ("978-0-19-562367-5", "The Discovery of India", "Jawaharlal Nehru", "History", 1946, 1),
    ("978-0-374-53355-7", "Thinking, Fast and Slow", "Daniel Kahneman", "Psychology", 2011, 2),
    ("978-0-7352-1129-2", "Atomic Habits", "James Clear", "Self-help", 2018, 3),
    ("978-1-5011-1132-3", "Deep Work", "Cal Newport", "Self-help", 2016, 1),
    ("978-0-553-38016-3", "A Brief History of Time", "Stephen Hawking", "Science", 1988, 2),
    ("978-0-393-35468-3", "The Gene", "Siddhartha Mukherjee", "Science", 2016, 1),
    ("978-0-14-044913-6", "Crime and Punishment", "Fyodor Dostoevsky", "Classics", 1866, 1),
    ("978-0-14-143951-8", "Pride and Prejudice", "Jane Austen", "Classics", 1813, 2),
    ("978-81-291-3577-0", "Wings of Fire", "A. P. J. Abdul Kalam", "Biography", 1999, 2),
]

MEMBERS = [
    ("Aanya Sharma", MemberTier.STUDENT),
    ("Vihaan Patel", MemberTier.STUDENT),
    ("Ishita Reddy", MemberTier.STUDENT),
    ("Arjun Nair", MemberTier.STUDENT),
    ("Diya Menon", MemberTier.STUDENT),
    ("Kabir Singh", MemberTier.STUDENT),
    ("Dr. Meera Iyer", MemberTier.FACULTY),
    ("Prof. Rohan Das", MemberTier.FACULTY),
    ("Dr. Sana Qureshi", MemberTier.FACULTY),
    ("Neha Kulkarni", MemberTier.PUBLIC),
    ("Farhan Ali", MemberTier.PUBLIC),
    ("Lakshmi Rao", MemberTier.PUBLIC),
]

DAYS_OF_HISTORY = 30


def seed() -> str:
    rng = random.Random(42)
    end = today()
    start = end - timedelta(days=DAYS_OF_HISTORY)

    with SessionLocal() as db:
        if db.scalar(select(func.count()).select_from(Book)):
            return "Database already has books; skipping seed."

        for isbn, title, author, genre, year, copies in BOOKS:
            db.add(
                Book(
                    isbn=isbn,
                    title=title,
                    author=author,
                    genre=genre,
                    published_year=year,
                    copies_total=copies,
                )
            )
        members = []
        for name, tier in MEMBERS:
            email = name.lower().replace("dr. ", "").replace("prof. ", "").replace(" ", ".")
            member = Member(
                full_name=name,
                email=f"{email}@example.org",
                tier=tier,
                card_number=f"tmp{len(members)}",
                joined_on=start - timedelta(days=rng.randint(30, 400)),
            )
            db.add(member)
            db.flush()
            member.card_number = card_number_for(member.id)
            members.append(member)
        db.commit()

        book_ids = list(db.scalars(select(Book.id)))
        member_ids = [m.id for m in members]

        for offset in range(DAYS_OF_HISTORY + 1):
            day = start + timedelta(days=offset)
            # Return some books; a few borrowers are habitually late.
            for loan in db.scalars(select(Loan).where(Loan.returned_on.is_(None))).all():
                late_bias = 6 if loan.member_id % 4 == 0 else 0
                if (
                    day
                    >= loan.due_on + timedelta(days=late_bias) - timedelta(days=rng.randint(0, 8))
                    and rng.random() < 0.45
                ):
                    circulation.return_loan(db, loan=loan, today=day)
                elif day >= loan.due_on - timedelta(days=1) and rng.random() < 0.15:
                    try:
                        circulation.renew(db, loan=loan, today=day)
                    except CirculationError:
                        db.rollback()

            # New checkouts, busier on weekdays; refused ones sometimes become holds.
            for _ in range(rng.randint(2, 6) if day.weekday() < 5 else rng.randint(0, 2)):
                book_id, member_id = rng.choice(book_ids), rng.choice(member_ids)
                try:
                    circulation.checkout(db, book_id=book_id, member_id=member_id, today=day)
                except CirculationError as refused:
                    db.rollback()
                    if refused.code == "NOT_AVAILABLE" and rng.random() < 0.6:
                        try:
                            hold = circulation.place_hold(
                                db, book_id=book_id, member_id=member_id, today=day
                            )
                            # Backdate to the simulated day so queue ages look real.
                            hour = time(rng.randint(9, 19), rng.randint(0, 59), tzinfo=UTC)
                            hold.placed_at = datetime.combine(day, hour)
                            db.commit()
                        except CirculationError:
                            db.rollback()

            # Members collect most READY holds within a day or two.
            for hold in db.scalars(select(Hold).where(Hold.status == HoldStatus.READY)).all():
                if rng.random() < 0.5:
                    try:
                        circulation.checkout(
                            db, book_id=hold.book_id, member_id=hold.member_id, today=day
                        )
                    except CirculationError:
                        db.rollback()

        # Settle most of the fines charged so far, leaving a few unpaid.
        for member in members:
            if rng.random() < 0.7:
                circulation.settle_fines(db, member=member, today=end)

        loans = db.scalar(select(func.count()).select_from(Loan))
        return f"Seeded {len(BOOKS)} books, {len(members)} members and {loans} loans."


if __name__ == "__main__":
    print(seed())
