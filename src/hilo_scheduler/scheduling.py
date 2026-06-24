from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .config import CANCELLATION_DEADLINE_HOURS, DEFAULT_DB_PATH, LESSON_MINUTES, SCHOOL_TZ
from .database import connect, connection, transaction
from .time_utils import (
    is_top_of_hour,
    local_display,
    local_midnight,
    minutes_since_midnight,
    parse_iso_datetime,
    parse_utc_iso,
    to_utc_iso,
    utc_now,
)


class SchedulingError(Exception):
    status_code = 400
    code = "scheduling_error"

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

    def to_dict(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message}}


class ValidationError(SchedulingError):
    status_code = 400
    code = "validation_error"


class NotFoundError(SchedulingError):
    status_code = 404
    code = "not_found"


class ConflictError(SchedulingError):
    status_code = 409
    code = "booking_conflict"


class LateCancellationError(SchedulingError):
    status_code = 409
    code = "late_cancellation"


class AuthorizationError(SchedulingError):
    status_code = 403
    code = "not_allowed"


@dataclass(frozen=True)
class ResourceWindow:
    resource_id: int
    weekday: int
    start_minute: int
    end_minute: int


def _window_rows(rows: Iterable[sqlite3.Row], resource_key: str) -> dict[int, list[ResourceWindow]]:
    windows: dict[int, list[ResourceWindow]] = {}
    for row in rows:
        resource_id = int(row[resource_key])
        windows.setdefault(resource_id, []).append(
            ResourceWindow(
                resource_id=resource_id,
                weekday=int(row["weekday"]),
                start_minute=minutes_since_midnight(row["start_time"]),
                end_minute=minutes_since_midnight(row["end_time"]),
            )
        )
    return windows


def _available_in_windows(
    windows: Iterable[ResourceWindow], weekday: int, start_minute: int, end_minute: int
) -> bool:
    return any(
        window.weekday == weekday
        and window.start_minute <= start_minute
        and end_minute <= window.end_minute
        for window in windows
    )


class Scheduler:
    """Application service that owns booking correctness and policy enforcement."""

    def __init__(
        self,
        db_path: str | Path = DEFAULT_DB_PATH,
        now_fn: Callable[[], datetime] = utc_now,
    ):
        self.db_path = Path(db_path)
        self._now_fn = now_fn

    def now(self) -> datetime:
        current = self._now_fn()
        if current.tzinfo is None:
            raise RuntimeError("now_fn must return an aware datetime")
        return current.astimezone(timezone.utc).replace(microsecond=0)

    def list_students(self) -> list[dict[str, Any]]:
        with connection(self.db_path) as conn:
            rows = conn.execute("SELECT id, name, email FROM students ORDER BY name").fetchall()
        return [dict(row) for row in rows]

    def list_instructors(self) -> list[dict[str, Any]]:
        with connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, name, certifications FROM instructors ORDER BY name"
            ).fetchall()
        return [dict(row) for row in rows]

    def list_aircraft(self) -> list[dict[str, Any]]:
        with connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, tail_number, model, equipment, active FROM aircraft ORDER BY tail_number"
            ).fetchall()
        return [dict(row) for row in rows]

    def get_availability(self, local_date: str, student_id: int | None = None) -> list[dict[str, Any]]:
        try:
            day = date.fromisoformat(local_date)
        except ValueError as exc:
            raise ValidationError("date must be in YYYY-MM-DD format") from exc

        if student_id is not None:
            self._require_student_exists(student_id)

        now = self.now()
        conn = connect(self.db_path)
        try:
            instructors = conn.execute(
                "SELECT id, name FROM instructors ORDER BY name"
            ).fetchall()
            aircraft = conn.execute(
                "SELECT id, tail_number, model FROM aircraft WHERE active = 1 ORDER BY tail_number"
            ).fetchall()
            instructor_windows = _window_rows(
                conn.execute(
                    "SELECT instructor_id, weekday, start_time, end_time FROM instructor_availability"
                ).fetchall(),
                "instructor_id",
            )
            aircraft_windows = _window_rows(
                conn.execute(
                    "SELECT aircraft_id, weekday, start_time, end_time FROM aircraft_availability"
                ).fetchall(),
                "aircraft_id",
            )
            day_start = local_midnight(day).astimezone(timezone.utc)
            day_end = day_start + timedelta(days=1)
            active_rows = conn.execute(
                """
                SELECT student_id, instructor_id, aircraft_id, start_utc
                FROM bookings
                WHERE status = 'active'
                  AND start_utc < ?
                  AND end_utc > ?
                """,
                (to_utc_iso(day_end), to_utc_iso(day_start)),
            ).fetchall()
        finally:
            conn.close()

        booked_instructors = {(row["instructor_id"], row["start_utc"]) for row in active_rows}
        booked_aircraft = {(row["aircraft_id"], row["start_utc"]) for row in active_rows}
        booked_students = {(row["student_id"], row["start_utc"]) for row in active_rows}

        slots: list[dict[str, Any]] = []
        cursor = local_midnight(day)
        for hour in range(24):
            start_local = cursor + timedelta(hours=hour)
            end_local = start_local + timedelta(minutes=LESSON_MINUTES)
            start_utc = start_local.astimezone(timezone.utc).replace(microsecond=0)
            end_utc = end_local.astimezone(timezone.utc).replace(microsecond=0)
            if start_utc <= now:
                continue

            start_minute = start_local.hour * 60 + start_local.minute
            end_minute = start_minute + LESSON_MINUTES
            if end_minute > 24 * 60:
                continue

            weekday = start_local.weekday()
            start_key = to_utc_iso(start_utc)
            if student_id is not None and (student_id, start_key) in booked_students:
                continue

            for instructor in instructors:
                instructor_id = int(instructor["id"])
                if (instructor_id, start_key) in booked_instructors:
                    continue
                if not _available_in_windows(
                    instructor_windows.get(instructor_id, []), weekday, start_minute, end_minute
                ):
                    continue

                for plane in aircraft:
                    aircraft_id = int(plane["id"])
                    if (aircraft_id, start_key) in booked_aircraft:
                        continue
                    if not _available_in_windows(
                        aircraft_windows.get(aircraft_id, []), weekday, start_minute, end_minute
                    ):
                        continue

                    slots.append(
                        {
                            "startUtc": start_key,
                            "endUtc": to_utc_iso(end_utc),
                            "startLocal": local_display(start_utc),
                            "endLocal": local_display(end_utc),
                            "studentId": student_id,
                            "instructorId": instructor_id,
                            "instructorName": instructor["name"],
                            "aircraftId": aircraft_id,
                            "tailNumber": plane["tail_number"],
                            "aircraftModel": plane["model"],
                        }
                    )
        return slots

    def book_lesson(
        self, student_id: int, instructor_id: int, aircraft_id: int, start_utc: str
    ) -> dict[str, Any]:
        start = parse_iso_datetime(start_utc)
        if not is_top_of_hour(start):
            raise ValidationError("lessons must start on an hourly boundary")
        if start <= self.now():
            raise ValidationError("cannot book a lesson in the past")

        end = start + timedelta(minutes=LESSON_MINUTES)
        created_at = self.now()

        with transaction(self.db_path) as conn:
            self._require_entities_exist(conn, student_id, instructor_id, aircraft_id)
            self._validate_resource_availability(conn, instructor_id, aircraft_id, start, end)
            self._validate_no_conflicts(conn, student_id, instructor_id, aircraft_id, start, end)
            try:
                cursor = conn.execute(
                    """
                    INSERT INTO bookings(
                        student_id, instructor_id, aircraft_id, start_utc, end_utc,
                        status, created_at_utc
                    )
                    VALUES (?, ?, ?, ?, ?, 'active', ?)
                    """,
                    (
                        student_id,
                        instructor_id,
                        aircraft_id,
                        to_utc_iso(start),
                        to_utc_iso(end),
                        to_utc_iso(created_at),
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise ConflictError(
                    "that slot was taken while your booking was being submitted"
                ) from exc
            booking_id = int(cursor.lastrowid)

        return self.get_booking(booking_id)

    def cancel_booking(
        self, booking_id: int, student_id: int | None = None, reason: str = "student_cancelled"
    ) -> dict[str, Any]:
        now = self.now()
        with transaction(self.db_path) as conn:
            booking = conn.execute(
                "SELECT * FROM bookings WHERE id = ? AND status = 'active'", (booking_id,)
            ).fetchone()
            if booking is None:
                raise NotFoundError("active booking not found")
            if student_id is not None and int(booking["student_id"]) != int(student_id):
                raise AuthorizationError("students can only cancel their own bookings")

            start = parse_utc_iso(booking["start_utc"])
            deadline = start - timedelta(hours=CANCELLATION_DEADLINE_HOURS)
            if now > deadline:
                raise LateCancellationError(
                    f"self-service cancellation closes {CANCELLATION_DEADLINE_HOURS} hours before lesson start"
                )

            conn.execute(
                """
                UPDATE bookings
                SET status = 'cancelled',
                    cancelled_at_utc = ?,
                    cancellation_reason = ?,
                    cancellation_policy_result = 'cancelled_before_deadline'
                WHERE id = ?
                """,
                (to_utc_iso(now), reason, booking_id),
            )

        return self.get_booking(booking_id, include_cancelled=True)

    def get_booking(self, booking_id: int, include_cancelled: bool = False) -> dict[str, Any]:
        status_filter = "" if include_cancelled else "AND b.status = 'active'"
        with connection(self.db_path) as conn:
            row = conn.execute(
                f"""
                SELECT b.*, s.name AS student_name, i.name AS instructor_name,
                       a.tail_number, a.model AS aircraft_model
                FROM bookings b
                JOIN students s ON s.id = b.student_id
                JOIN instructors i ON i.id = b.instructor_id
                JOIN aircraft a ON a.id = b.aircraft_id
                WHERE b.id = ? {status_filter}
                """,
                (booking_id,),
            ).fetchone()
        if row is None:
            raise NotFoundError("booking not found")
        return self._serialize_booking(row)

    def list_bookings(
        self, student_id: int | None = None, status: str | None = "active"
    ) -> list[dict[str, Any]]:
        filters: list[str] = []
        params: list[Any] = []
        if student_id is not None:
            filters.append("b.student_id = ?")
            params.append(student_id)
        if status:
            if status not in {"active", "cancelled"}:
                raise ValidationError("status must be active, cancelled, or empty")
            filters.append("b.status = ?")
            params.append(status)
        where = "WHERE " + " AND ".join(filters) if filters else ""
        with connection(self.db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT b.*, s.name AS student_name, i.name AS instructor_name,
                       a.tail_number, a.model AS aircraft_model
                FROM bookings b
                JOIN students s ON s.id = b.student_id
                JOIN instructors i ON i.id = b.instructor_id
                JOIN aircraft a ON a.id = b.aircraft_id
                {where}
                ORDER BY b.start_utc, b.id
                """,
                params,
            ).fetchall()
        return [self._serialize_booking(row) for row in rows]

    def _require_student_exists(self, student_id: int) -> None:
        with connection(self.db_path) as conn:
            row = conn.execute("SELECT id FROM students WHERE id = ?", (student_id,)).fetchone()
        if row is None:
            raise NotFoundError("student not found")

    def _require_entities_exist(
        self, conn: sqlite3.Connection, student_id: int, instructor_id: int, aircraft_id: int
    ) -> None:
        if conn.execute("SELECT 1 FROM students WHERE id = ?", (student_id,)).fetchone() is None:
            raise NotFoundError("student not found")
        if conn.execute("SELECT 1 FROM instructors WHERE id = ?", (instructor_id,)).fetchone() is None:
            raise NotFoundError("instructor not found")
        if (
            conn.execute(
                "SELECT 1 FROM aircraft WHERE id = ? AND active = 1", (aircraft_id,)
            ).fetchone()
            is None
        ):
            raise NotFoundError("active aircraft not found")

    def _validate_resource_availability(
        self,
        conn: sqlite3.Connection,
        instructor_id: int,
        aircraft_id: int,
        start: datetime,
        end: datetime,
    ) -> None:
        start_local = start.astimezone(SCHOOL_TZ)
        end_local = end.astimezone(SCHOOL_TZ)
        if start_local.date() != end_local.date():
            raise ValidationError("lesson must fit within one school-local calendar day")
        start_minute = start_local.hour * 60 + start_local.minute
        end_minute = start_minute + LESSON_MINUTES
        weekday = start_local.weekday()

        instructor_rows = conn.execute(
            """
            SELECT instructor_id, weekday, start_time, end_time
            FROM instructor_availability
            WHERE instructor_id = ? AND weekday = ?
            """,
            (instructor_id, weekday),
        ).fetchall()
        aircraft_rows = conn.execute(
            """
            SELECT aircraft_id, weekday, start_time, end_time
            FROM aircraft_availability
            WHERE aircraft_id = ? AND weekday = ?
            """,
            (aircraft_id, weekday),
        ).fetchall()
        instructor_windows = _window_rows(instructor_rows, "instructor_id").get(instructor_id, [])
        aircraft_windows = _window_rows(aircraft_rows, "aircraft_id").get(aircraft_id, [])
        if not _available_in_windows(instructor_windows, weekday, start_minute, end_minute):
            raise ValidationError("instructor is not available for that one-hour slot")
        if not _available_in_windows(aircraft_windows, weekday, start_minute, end_minute):
            raise ValidationError("aircraft is not available for that one-hour slot")

    def _validate_no_conflicts(
        self,
        conn: sqlite3.Connection,
        student_id: int,
        instructor_id: int,
        aircraft_id: int,
        start: datetime,
        end: datetime,
    ) -> None:
        start_iso = to_utc_iso(start)
        end_iso = to_utc_iso(end)
        conflicts = conn.execute(
            """
            SELECT id, student_id, instructor_id, aircraft_id
            FROM bookings
            WHERE status = 'active'
              AND start_utc < ?
              AND end_utc > ?
              AND (student_id = ? OR instructor_id = ? OR aircraft_id = ?)
            """,
            (end_iso, start_iso, student_id, instructor_id, aircraft_id),
        ).fetchall()
        if conflicts:
            conflict = conflicts[0]
            if int(conflict["student_id"]) == student_id:
                raise ConflictError("student already has an active booking at that time")
            if int(conflict["instructor_id"]) == instructor_id:
                raise ConflictError("instructor already has an active booking at that time")
            if int(conflict["aircraft_id"]) == aircraft_id:
                raise ConflictError("aircraft already has an active booking at that time")
            raise ConflictError("slot is no longer available")

    def _serialize_booking(self, row: sqlite3.Row) -> dict[str, Any]:
        start = parse_utc_iso(row["start_utc"])
        end = parse_utc_iso(row["end_utc"])
        deadline = start - timedelta(hours=CANCELLATION_DEADLINE_HOURS)
        can_cancel = row["status"] == "active" and self.now() <= deadline
        return {
            "id": int(row["id"]),
            "studentId": int(row["student_id"]),
            "studentName": row["student_name"],
            "instructorId": int(row["instructor_id"]),
            "instructorName": row["instructor_name"],
            "aircraftId": int(row["aircraft_id"]),
            "tailNumber": row["tail_number"],
            "aircraftModel": row["aircraft_model"],
            "startUtc": row["start_utc"],
            "endUtc": row["end_utc"],
            "startLocal": local_display(start),
            "endLocal": local_display(end),
            "status": row["status"],
            "createdAtUtc": row["created_at_utc"],
            "cancelledAtUtc": row["cancelled_at_utc"],
            "cancellationReason": row["cancellation_reason"],
            "cancellationPolicyResult": row["cancellation_policy_result"],
            "cancelDeadlineUtc": to_utc_iso(deadline),
            "canCancelSelfService": can_cancel,
        }
