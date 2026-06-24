from __future__ import annotations

import sys
from pathlib import Path

# Add project root to sys.path so src.hilo_scheduler is importable
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.hilo_scheduler.api import HiloRequestHandler  # noqa: E402
from src.hilo_scheduler.config import STATIC_ROOT  # noqa: E402
from src.hilo_scheduler.database import initialize_database  # noqa: E402

# Vercel's container filesystem is read-only except /tmp.
# SQLite lives there — data is ephemeral across cold starts (demo use only).
# For persistence, swap this for a hosted database (Supabase, Neon, etc.).
_DB_PATH = Path("/tmp/hilo_scheduler.sqlite3")

# Runs once per container lifetime (cold start), not per request.
initialize_database(_DB_PATH)


class handler(HiloRequestHandler):
    """Vercel serverless adapter — thin subclass of HiloRequestHandler."""

    scheduler_db_path = _DB_PATH
    static_root = STATIC_ROOT
