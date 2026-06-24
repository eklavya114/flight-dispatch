from __future__ import annotations

from pathlib import Path

from .config import DEFAULT_DB_PATH
from .database import connect

STUDENTS = [
    (1, "Maya Chen", "maya.chen@example.test"),
    (2, "Noah Patel", "noah.patel@example.test"),
    (3, "Ava Torres", "ava.torres@example.test"),
    (4, "Liam Johnson", "liam.johnson@example.test"),
]

INSTRUCTORS = [
    (1, "Amelia Hart", "CFI, CFII"),
    (2, "Marcus Lee", "CFI, Instrument"),
    (3, "Sofia Rivera", "CFI, Commercial"),
]

AIRCRAFT = [
    (1, "N172HA", "Cessna 172S", "G1000"),
    (2, "N739FS", "Piper PA-28 Archer", "IFR trainer"),
]

# Python weekday numbers: Monday=0, Sunday=6.
INSTRUCTOR_AVAILABILITY = [
    # Amelia: mornings plus an overlapping Wednesday block.
    (1, 0, "08:00", "12:00"),
    (1, 2, "10:00", "15:00"),
    (1, 4, "08:00", "12:00"),
    (1, 5, "09:00", "12:00"),
    # Marcus: after-school/evening demand windows.
    (2, 0, "15:00", "20:00"),
    (2, 1, "08:00", "12:00"),
    (2, 3, "15:00", "20:00"),
    (2, 5, "08:00", "13:00"),
    # Sofia: mixed availability and overlap with Amelia on Wednesday.
    (3, 1, "15:00", "20:00"),
    (3, 2, "08:00", "12:00"),
    (3, 3, "09:00", "14:00"),
    (3, 4, "13:00", "18:00"),
]

AIRCRAFT_AVAILABILITY = [
    # N172HA is the high-utilization trainer.
    (1, 0, "08:00", "20:00"),
    (1, 1, "08:00", "20:00"),
    (1, 2, "08:00", "20:00"),
    (1, 3, "08:00", "20:00"),
    (1, 4, "08:00", "20:00"),
    (1, 5, "08:00", "14:00"),
    # N739FS has a Wednesday afternoon maintenance window.
    (2, 0, "10:00", "20:00"),
    (2, 1, "10:00", "20:00"),
    (2, 2, "08:00", "14:00"),
    (2, 3, "10:00", "20:00"),
    (2, 4, "10:00", "18:00"),
    (2, 5, "09:00", "13:00"),
]


def seed_demo_data(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    conn = connect(db_path)
    try:
        existing = conn.execute("SELECT COUNT(*) AS count FROM students").fetchone()["count"]
        if existing:
            return

        conn.execute("BEGIN")
        conn.executemany("INSERT INTO students(id, name, email) VALUES (?, ?, ?)", STUDENTS)
        conn.executemany(
            "INSERT INTO instructors(id, name, certifications) VALUES (?, ?, ?)", INSTRUCTORS
        )
        conn.executemany(
            "INSERT INTO aircraft(id, tail_number, model, equipment) VALUES (?, ?, ?, ?)", AIRCRAFT
        )
        conn.executemany(
            """
            INSERT INTO instructor_availability(instructor_id, weekday, start_time, end_time)
            VALUES (?, ?, ?, ?)
            """,
            INSTRUCTOR_AVAILABILITY,
        )
        conn.executemany(
            """
            INSERT INTO aircraft_availability(aircraft_id, weekday, start_time, end_time)
            VALUES (?, ?, ?, ?)
            """,
            AIRCRAFT_AVAILABILITY,
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
