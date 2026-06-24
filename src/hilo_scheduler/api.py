from __future__ import annotations

import json
import mimetypes
import re
import traceback
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .config import DEFAULT_DB_PATH, STATIC_ROOT
from .database import initialize_database
from .scheduling import Scheduler, SchedulingError, ValidationError
import subprocess

BOOKING_PATH = re.compile(r"^/api/bookings/(\d+)$")


def create_server(
    host: str = "127.0.0.1",
    port: int = 8080,
    db_path: str | Path = DEFAULT_DB_PATH,
    static_root: str | Path = STATIC_ROOT,
) -> ThreadingHTTPServer:
    db_path = Path(db_path)
    static_root = Path(static_root)
    initialize_database(db_path)

    handler_db_path = db_path
    handler_static_root = static_root

    class Handler(HiloRequestHandler):
        scheduler_db_path = handler_db_path
        static_root = handler_static_root

    return ThreadingHTTPServer((host, port), Handler)


def run_server(host: str = "127.0.0.1", port: int = 8080, db_path: str | Path = DEFAULT_DB_PATH) -> None:
    server = create_server(host, port, db_path)
    address = server.server_address
    print(f"Hilo Flight Scheduler running at http://{address[0]}:{address[1]}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


class HiloRequestHandler(BaseHTTPRequestHandler):
    scheduler_db_path: Path = DEFAULT_DB_PATH
    static_root: Path = STATIC_ROOT
    server_version = "HiloFlightScheduler/1.0"

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self._send_common_headers("application/json")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        self._dispatch("GET")

    def do_POST(self) -> None:
        self._dispatch("POST")

    def do_DELETE(self) -> None:
        self._dispatch("DELETE")

    def _dispatch(self, method: str) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        scheduler = Scheduler(self.scheduler_db_path)

        try:
            if method == "GET" and path == "/api/health":
                self._send_json({"ok": True, "service": "hilo-flight-scheduler"})
                return
            if method == "GET" and path == "/api/students":
                self._send_json({"students": scheduler.list_students()})
                return
            if method == "GET" and path == "/api/instructors":
                self._send_json({"instructors": scheduler.list_instructors()})
                return
            if method == "GET" and path == "/api/aircraft":
                self._send_json({"aircraft": scheduler.list_aircraft()})
                return
            if method == "GET" and path == "/api/availability":
                day = self._first(query, "date")
                if not day:
                    raise ValidationError("date query parameter is required")
                student_id = self._optional_int(query, "student_id")
                slots = scheduler.get_availability(day, student_id=student_id)
                self._send_json({"date": day, "slots": slots})
                return
            if method == "GET" and path == "/api/docs":
                # Serve project README as simple HTML for local dev convenience
                readme = (self.static_root.resolve().parent / "README.md")
                if not readme.exists():
                    self._send_json({"error": {"code": "not_found", "message": "README not found"}}, status=HTTPStatus.NOT_FOUND)
                    return
                text = readme.read_text(encoding="utf-8")
                html = f"<html><head><meta charset=\"utf-8\"><title>Docs</title></head><body><pre style=\"white-space:pre-wrap;font-family:system-ui,Segoe UI,Roboto,Arial;\">{text}</pre></body></html>"
                data = html.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self._send_common_headers("text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
                return
            if method == "GET" and path == "/api/run-tests":
                # Run the unit tests and return output (for local dev only)
                try:
                    result = subprocess.run(["python", "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=str(self.static_root.resolve().parent), capture_output=True, text=True, timeout=60)
                    output = result.stdout + "\n" + result.stderr
                    self._send_json({"exit_code": result.returncode, "output": output})
                except Exception as exc:
                    self._send_json({"error": {"code": "test_error", "message": str(exc)}}, status=HTTPStatus.INTERNAL_SERVER_ERROR)
                return
            if path == "/api/bookings" and method == "GET":
                student_id = self._optional_int(query, "student_id")
                status = self._first(query, "status", "active")
                if status == "all":
                    status = None
                self._send_json({"bookings": scheduler.list_bookings(student_id, status)})
                return
            if path == "/api/bookings" and method == "POST":
                body = self._read_json()
                booking = scheduler.book_lesson(
                    student_id=int(body["studentId"]),
                    instructor_id=int(body["instructorId"]),
                    aircraft_id=int(body["aircraftId"]),
                    start_utc=str(body["startUtc"]),
                )
                self._send_json({"booking": booking}, status=HTTPStatus.CREATED)
                return
            booking_match = BOOKING_PATH.match(path)
            if booking_match and method == "DELETE":
                body = self._read_json(required=False)
                student_id = self._optional_int(query, "student_id")
                if student_id is None and body and "studentId" in body:
                    student_id = int(body["studentId"])
                reason = str(body.get("reason", "student_cancelled")) if body else "student_cancelled"
                booking = scheduler.cancel_booking(int(booking_match.group(1)), student_id, reason)
                self._send_json({"booking": booking})
                return
            if method == "GET" and (path == "/" or path.startswith("/static/")):
                self._serve_static(path)
                return
            self._send_json(
                {"error": {"code": "not_found", "message": "route not found"}},
                status=HTTPStatus.NOT_FOUND,
            )
        except SchedulingError as exc:
            self._send_json(exc.to_dict(), status=exc.status_code)
        except (KeyError, TypeError, ValueError) as exc:
            self._send_json(
                {"error": {"code": "bad_request", "message": str(exc)}},
                status=HTTPStatus.BAD_REQUEST,
            )
        except Exception as exc:
            traceback.print_exc()
            self._send_json(
                {"error": {"code": "server_error", "message": "unexpected server error"}},
                status=HTTPStatus.INTERNAL_SERVER_ERROR,
            )

    def _serve_static(self, path: str) -> None:
        if path == "/":
            target = self.static_root / "index.html"
        else:
            relative = path.removeprefix("/static/")
            target = (self.static_root / relative).resolve()
            if self.static_root.resolve() not in target.parents:
                self._send_json(
                    {"error": {"code": "not_found", "message": "asset not found"}},
                    status=HTTPStatus.NOT_FOUND,
                )
                return
        if not target.exists() or not target.is_file():
            self._send_json(
                {"error": {"code": "not_found", "message": "asset not found"}},
                status=HTTPStatus.NOT_FOUND,
            )
            return
        content_type = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self.send_response(HTTPStatus.OK)
        self._send_common_headers(content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_json(self, payload: dict[str, Any], status: int | HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(int(status))
        self._send_common_headers("application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _send_common_headers(self, content_type: str) -> None:
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")

    def _read_json(self, required: bool = True) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0"))
        if length == 0:
            if required:
                raise ValueError("JSON request body is required")
            return {}
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("request body must be valid JSON") from exc
        if not isinstance(parsed, dict):
            raise ValueError("JSON request body must be an object")
        return parsed

    @staticmethod
    def _first(query: dict[str, list[str]], key: str, default: str | None = None) -> str | None:
        values = query.get(key)
        return values[0] if values else default

    @classmethod
    def _optional_int(cls, query: dict[str, list[str]], key: str) -> int | None:
        value = cls._first(query, key)
        return int(value) if value not in (None, "") else None

    def log_message(self, format: str, *args: Any) -> None:
        # Keep local runs readable. Uncomment the next line while debugging HTTP traffic.
        # super().log_message(format, *args)
        return
