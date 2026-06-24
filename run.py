from __future__ import annotations

import argparse
from pathlib import Path

from src.hilo_scheduler.api import run_server
from src.hilo_scheduler.config import DEFAULT_DB_PATH
from src.hilo_scheduler.database import initialize_database


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the Hilo Flight Scheduler demo app.")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind. Default: 127.0.0.1")
    parser.add_argument("--port", type=int, default=8080, help="Port to bind. Default: 8080")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite database path")
    parser.add_argument("--init-db", action="store_true", help="Initialize/seed the database and exit")
    parser.add_argument("--reset-db", action="store_true", help="Delete and recreate the database before running")
    args = parser.parse_args()

    initialize_database(args.db, reset=args.reset_db)
    print(f"Database ready: {args.db}")
    if args.init_db:
        return

    run_server(args.host, args.port, args.db)


if __name__ == "__main__":
    main()
