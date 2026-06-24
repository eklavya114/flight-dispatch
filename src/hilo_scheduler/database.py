from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from .config import DEFAULT_DB_PATH

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS instructors (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    certifications TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS aircraft (
    id INTEGER PRIMARY KEY,
    tail_number TEXT NOT NULL UNIQUE,
    model TEXT NOT NULL,
    equipment TEXT NOT NULL DEFAULT '',
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS instructor_availability (
    id INTEGER PRIMARY KEY,
    instructor_id INTEGER NOT NULL REFERENCES instructors(id) ON DELETE CASCADE,
    weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    start_time TEXT NOT NULL CHECK (length(start_time) = 5),
    end_time TEXT NOT NULL CHECK (length(end_time) = 5),
    CHECK (start_time < end_time)
);

CREATE TABLE IF NOT EXISTS aircraft_availability (
    id INTEGER PRIMARY KEY,
    aircraft_id INTEGER NOT NULL REFERENCES aircraft(id) ON DELETE CASCADE,
    weekday INTEGER NOT NULL CHECK (weekday BETWEEN 0 AND 6),
    start_time TEXT NOT NULL CHECK (length(start_time) = 5),
    end_time TEXT NOT NULL CHECK (length(end_time) = 5),
    CHECK (start_time < end_time)
);

CREATE TABLE IF NOT EXISTS bookings (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES students(id),
    instructor_id INTEGER NOT NULL REFERENCES instructors(id),
    aircraft_id INTEGER NOT NULL REFERENCES aircraft(id),
    start_utc TEXT NOT NULL,
    end_utc TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled')),
    created_at_utc TEXT NOT NULL,
    cancelled_at_utc TEXT,
    cancellation_reason TEXT,
    cancellation_policy_result TEXT,
    CHECK (start_utc < end_utc),
    CHECK (status = 'active' OR cancelled_at_utc IS NOT NULL)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_active_instructor_slot
    ON bookings(instructor_id, start_utc)
    WHERE status = 'active';

CREATE UNIQUE INDEX IF NOT EXISTS ux_active_aircraft_slot
    ON bookings(aircraft_id, start_utc)
    WHERE status = 'active';

CREATE UNIQUE INDEX IF NOT EXISTS ux_active_student_slot
    ON bookings(student_id, start_utc)
    WHERE status = 'active';

CREATE INDEX IF NOT EXISTS ix_bookings_active_range
    ON bookings(status, start_utc, end_utc);

CREATE INDEX IF NOT EXISTS ix_instructor_availability_lookup
    ON instructor_availability(instructor_id, weekday);

CREATE INDEX IF NOT EXISTS ix_aircraft_availability_lookup
    ON aircraft_availability(aircraft_id, weekday);
"""


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path = str(db_path)
    conn = sqlite3.connect(db_path, timeout=10, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    if db_path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    return conn


def initialize_database(db_path: str | Path = DEFAULT_DB_PATH, reset: bool = False) -> None:
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if reset and db_path.exists():
        db_path.unlink()

    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()

    from .seed import seed_demo_data

    seed_demo_data(db_path)


@contextmanager
def connection(db_path: str | Path = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction(db_path: str | Path = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = connect(db_path)
    try:
        conn.execute("BEGIN IMMEDIATE")
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
