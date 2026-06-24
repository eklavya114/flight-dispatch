from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from src.hilo_scheduler.api import create_server
from src.hilo_scheduler.database import initialize_database


class ApiSmokeTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "api.sqlite3"
        initialize_database(self.db_path, reset=True)
        self.server = create_server("127.0.0.1", 0, self.db_path)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.tmp.cleanup()

    def get_json(self, path: str):
        with urlopen(self.base_url + path, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def send_json(self, method: str, path: str, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        request = Request(
            self.base_url + path,
            data=data,
            method=method,
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_health_availability_booking_and_cancel_flow(self) -> None:
        health = self.get_json("/api/health")
        self.assertTrue(health["ok"])

        query = urlencode({"date": "2026-06-17", "student_id": 1})
        availability = self.get_json(f"/api/availability?{query}")
        slot = next(
            s
            for s in availability["slots"]
            if s["instructorId"] == 1 and s["aircraftId"] == 1
        )

        created = self.send_json(
            "POST",
            "/api/bookings",
            {
                "studentId": 1,
                "instructorId": slot["instructorId"],
                "aircraftId": slot["aircraftId"],
                "startUtc": slot["startUtc"],
            },
        )
        self.assertEqual(created["booking"]["status"], "active")

        bookings = self.get_json("/api/bookings?student_id=1")
        self.assertEqual(len(bookings["bookings"]), 1)

        cancelled = self.send_json(
            "DELETE",
            f"/api/bookings/{created['booking']['id']}?student_id=1",
            {"reason": "student_requested"},
        )
        self.assertEqual(cancelled["booking"]["status"], "cancelled")


if __name__ == "__main__":
    unittest.main()
