from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

from .config import SCHOOL_TZ


def utc_now() -> datetime:
    """Return an aware UTC datetime."""
    return datetime.now(timezone.utc).replace(microsecond=0)


def parse_iso_datetime(value: str) -> datetime:
    """Parse an ISO timestamp and normalize it to aware UTC seconds."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("start time is required")

    cleaned = value.strip()
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1] + "+00:00"

    parsed = datetime.fromisoformat(cleaned)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone offset or Z")
    return parsed.astimezone(timezone.utc).replace(microsecond=0)


def to_utc_iso(value: datetime) -> str:
    """Format an aware datetime as a stable UTC ISO string for SQLite."""
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_utc_iso(value: str) -> datetime:
    return parse_iso_datetime(value)


def local_date_bounds_utc(day: date) -> tuple[datetime, datetime]:
    local_start = datetime.combine(day, time(0, 0)).replace(tzinfo=SCHOOL_TZ)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(timezone.utc), local_end.astimezone(timezone.utc)


def local_midnight(day: date) -> datetime:
    return datetime.combine(day, time(0, 0)).replace(tzinfo=SCHOOL_TZ)


def minutes_since_midnight(value: str) -> int:
    hour, minute = value.split(":", 1)
    return int(hour) * 60 + int(minute)


def is_top_of_hour(value: datetime) -> bool:
    return value.minute == 0 and value.second == 0 and value.microsecond == 0


def local_display(value: datetime) -> str:
    return value.astimezone(SCHOOL_TZ).strftime("%Y-%m-%d %H:%M %Z")
