from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

APP_NAME = "Hilo Flight Scheduler"
SCHOOL_TIME_ZONE = "Pacific/Honolulu"
SCHOOL_TZ = ZoneInfo(SCHOOL_TIME_ZONE)
LESSON_MINUTES = 60
CANCELLATION_DEADLINE_HOURS = 12

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "hilo_scheduler.sqlite3"
STATIC_ROOT = PROJECT_ROOT / "static"
