from __future__ import annotations

import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src.hilo_scheduler.database import connect, connection, initialize_database
from src.hilo_scheduler.scheduling import (
    ConflictError,
    LateCancellationError,
    Scheduler,
    ValidationError,
)
from src.hilo_scheduler.time_utils import parse_iso_datetime, to_utc_iso


class MutableClock:
    def __init__(self, current: datetime):
        self.current = current

    def now(self) -> datetime:
        return self.current

    def set(self, current: datetime) -> None:
        self.current = current


class SchedulerTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "scheduler.sqlite3"
        initialize_database(self.db_path, reset=True)
        self.clock = MutableClock(datetime(2026, 6, 1, 0, 0, tzinfo=timezone.utc))
        self.scheduler = Scheduler(self.db_path, now_fn=self.clock.now)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def first_slot(self, day: str, *, student_id: int = 1, instructor_id: int | None = None, aircraft_id: int | None = None):
        slots = self.scheduler.get_availability(day, student_id=student_id)
        for slot in slots:
            if instructor_id is not None and slot["instructorId"] != instructor_id:
                continue
            if aircraft_id is not None and slot["aircraftId"] != aircraft_id:
                continue
            return slot
        self.fail(f"No slot found for day={day}, instructor={instructor_id}, aircraft={aircraft_id}")

    def test_availability_returns_seeded_real_combinations(self) -> None:
        slots = self.scheduler.get_availability("2026-06-17", student_id=1)

        self.assertGreater(len(slots), 0)
        example = slots[0]
        self.assertIn("startUtc", example)
        self.assertIn("instructorName", example)
        self.assertIn("tailNumber", example)
        self.assertEqual(example["studentId"], 1)
        self.assertTrue(any(s["instructorName"] == "Amelia Hart" for s in slots))
        self.assertTrue(any(s["instructorName"] == "Sofia Rivera" for s in slots))

    def test_booking_valid_slot_removes_conflicting_resources_from_availability(self) -> None:
        slot = self.first_slot("2026-06-17", student_id=1, instructor_id=1, aircraft_id=1)

        booking = self.scheduler.book_lesson(1, slot["instructorId"], slot["aircraftId"], slot["startUtc"])

        self.assertEqual(booking["status"], "active")
        self.assertEqual(booking["studentId"], 1)
        follow_up_slots = self.scheduler.get_availability("2026-06-17", student_id=2)
        self.assertFalse(
            any(
                s["startUtc"] == slot["startUtc"]
                and (s["instructorId"] == slot["instructorId"] or s["aircraftId"] == slot["aircraftId"])
                for s in follow_up_slots
            )
        )

    def test_prevents_instructor_aircraft_and_student_conflicts(self) -> None:
        slot = self.first_slot("2026-06-17", student_id=1, instructor_id=1, aircraft_id=1)
        self.scheduler.book_lesson(1, 1, 1, slot["startUtc"])

        with self.assertRaises(ConflictError):
            self.scheduler.book_lesson(2, 1, 2, slot["startUtc"])

        with self.assertRaises(ConflictError):
            self.scheduler.book_lesson(2, 3, 1, slot["startUtc"])

        with self.assertRaises(ConflictError):
            self.scheduler.book_lesson(1, 3, 2, slot["startUtc"])

    def test_concurrent_booking_same_slot_has_single_winner(self) -> None:
        slot = self.first_slot("2026-06-17", student_id=1, instructor_id=1, aircraft_id=1)
        with connection(self.db_path) as conn:
            conn.execute("BEGIN")
            for student_id in range(10, 22):
                conn.execute(
                    "INSERT INTO students(id, name, email) VALUES (?, ?, ?)",
                    (student_id, f"Concurrent Student {student_id}", f"student{student_id}@example.test"),
                )
            conn.commit()

        def attempt(student_id: int) -> bool:
            local_scheduler = Scheduler(self.db_path, now_fn=self.clock.now)
            try:
                local_scheduler.book_lesson(student_id, 1, 1, slot["startUtc"])
                return True
            except ConflictError:
                return False

        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(attempt, range(10, 22)))

        self.assertEqual(results.count(True), 1)
        with connection(self.db_path) as conn:
            count = conn.execute(
                """
                SELECT COUNT(*) AS count
                FROM bookings
                WHERE status = 'active' AND instructor_id = 1 AND aircraft_id = 1 AND start_utc = ?
                """,
                (slot["startUtc"],),
            ).fetchone()["count"]
        self.assertEqual(count, 1)

    def test_cancellation_before_deadline_releases_the_slot(self) -> None:
        slot = self.first_slot("2026-06-17", student_id=1, instructor_id=1, aircraft_id=1)
        booking = self.scheduler.book_lesson(1, 1, 1, slot["startUtc"])
        start = parse_iso_datetime(slot["startUtc"])
        self.clock.set(start - timedelta(hours=24))

        cancelled = self.scheduler.cancel_booking(booking["id"], student_id=1)
        replacement = self.scheduler.book_lesson(2, 1, 1, slot["startUtc"])

        self.assertEqual(cancelled["status"], "cancelled")
        self.assertEqual(replacement["status"], "active")
        self.assertEqual(replacement["studentId"], 2)

    def test_late_cancellation_is_rejected_and_booking_stays_active(self) -> None:
        slot = self.first_slot("2026-06-17", student_id=1, instructor_id=1, aircraft_id=1)
        booking = self.scheduler.book_lesson(1, 1, 1, slot["startUtc"])
        start = parse_iso_datetime(slot["startUtc"])
        self.clock.set(start - timedelta(hours=6))

        with self.assertRaises(LateCancellationError):
            self.scheduler.cancel_booking(booking["id"], student_id=1)

        active = self.scheduler.get_booking(booking["id"])
        self.assertEqual(active["status"], "active")
        self.assertFalse(active["canCancelSelfService"])

    def test_rejects_booking_outside_availability(self) -> None:
        sunday_hawaii_10am = "2026-06-21T20:00:00Z"

        with self.assertRaises(ValidationError):
            self.scheduler.book_lesson(1, 1, 1, sunday_hawaii_10am)

    def test_rejects_non_hour_boundary(self) -> None:
        slot = self.first_slot("2026-06-17", student_id=1, instructor_id=1, aircraft_id=1)
        start = parse_iso_datetime(slot["startUtc"]) + timedelta(minutes=30)

        with self.assertRaises(ValidationError):
            self.scheduler.book_lesson(1, 1, 1, to_utc_iso(start))


if __name__ == "__main__":
    unittest.main()
