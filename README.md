# Aerodesk

**Flight school scheduling engine.** Instructor availability, aircraft dispatch, and student lesson booking with conflict-safe SQLite transactions — zero runtime dependencies, runs from a clean checkout.

---

## What it does

Aerodesk solves the core scheduling invariants of a small flight school:

- A student can book exactly one instructor and one aircraft for a one-hour block
- No instructor or aircraft can be double-booked at the same hour
- Self-service cancellations are rejected within 12 hours of the lesson
- Concurrent booking attempts are serialised at the database layer — no race condition can produce a double booking

The frontend is a real-time dispatch console: filter by instructor, aircraft, or time window, see the timeline fill as slots are taken, and book or cancel in one click.

---

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11+, standard library only (`http.server`, `sqlite3`, `json`) |
| Database | SQLite 3 with WAL mode, `BEGIN IMMEDIATE` transactions, partial unique indexes |
| Frontend | Vanilla HTML / CSS / JS — no framework, no build step |
| Tests | `unittest` (standard library) |

No `pip install` required. If you have Python 3.11, you can run it.

---

## Quick start

```bash
git clone https://github.com/<you>/aerodesk.git
cd aerodesk
python run.py
```

Open **http://127.0.0.1:8080**

The database is created and seeded automatically on first run.

### Options

```bash
python run.py                        # start server (default: 127.0.0.1:8080)
python run.py --host 0.0.0.0         # listen on all interfaces
python run.py --port 3000            # custom port
python run.py --reset-db             # wipe and reseed the database
python run.py --init-db              # initialise DB without starting server
```

### Run the test suite

```bash
python -m unittest discover -s tests -v
```

Or hit the **Tests** button in the UI to run the suite server-side and see output in a modal.

---

## Seeded data

The database ships with enough demo data to exercise every code path:

| Type | Records |
|---|---|
| Students | Maya Chen, Noah Patel, Ava Torres, Liam Johnson |
| Instructors | Amelia Hart (CFI/CFII), Marcus Lee (CFI/Instrument), Sofia Rivera (CFI/Commercial) |
| Aircraft | N172HA — Cessna 172S, N739FS — Piper PA-28 Archer |

**Best test date:** any upcoming Wednesday. All three instructors and both aircraft are available, with intentional overlapping windows to exercise conflict resolution.

---

## API reference

All responses are `application/json`. Errors return `{ "error": { "code": "...", "message": "..." } }`.

### Health

```
GET /api/health
→ { "ok": true, "service": "hilo-flight-scheduler" }
```

### Roster

```
GET /api/students
GET /api/instructors
GET /api/aircraft          # active aircraft only
```

### Availability

```
GET /api/availability?date=YYYY-MM-DD&student_id=1
```

Returns every valid `(hour, instructor, aircraft)` combination for the given date and student. Excludes slots where the instructor, aircraft, or student is already booked.

**Response shape:**

```json
{
  "slots": [
    {
      "startUtc":      "2026-06-25T20:00:00Z",
      "endUtc":        "2026-06-25T21:00:00Z",
      "startLocal":    "2026-06-25 10:00 AM HST",
      "endLocal":      "2026-06-25 11:00 AM HST",
      "instructorId":  1,
      "instructorName":"Amelia Hart",
      "aircraftId":    1,
      "tailNumber":    "N172HA",
      "aircraftModel": "Cessna 172S"
    }
  ]
}
```

### Bookings

```
GET  /api/bookings?student_id=1&status=active
POST /api/bookings
DELETE /api/bookings/{id}?student_id=1
```

**POST body:**

```json
{
  "studentId":    1,
  "instructorId": 1,
  "aircraftId":   1,
  "startUtc":     "2026-06-25T20:00:00Z"
}
```

**DELETE body:**

```json
{ "reason": "student_requested" }
```

Cancellations within 12 hours of lesson start return `409 Conflict` with code `late_cancellation`.

### Error codes

| HTTP | Code | Meaning |
|---|---|---|
| 400 | `validation_error` | Missing or invalid fields |
| 404 | `not_found` | Student / instructor / aircraft not found |
| 409 | `conflict` | Slot already booked |
| 409 | `late_cancellation` | Within 12-hour cancellation window |
| 403 | `authorization_error` | Student does not own this booking |

---

## Database schema

```sql
students          (id, name, email)
instructors       (id, name, certifications)
aircraft          (id, tail_number, model, equipment, active)

instructor_availability   (instructor_id, weekday 0-6, start_time, end_time)
aircraft_availability     (aircraft_id,   weekday 0-6, start_time, end_time)

bookings (
  id, student_id, instructor_id, aircraft_id,
  start_utc, end_utc,
  status CHECK(status IN ('active','cancelled')),
  created_at_utc, cancelled_at_utc, cancellation_reason,
  cancel_deadline_utc, can_cancel_self_service
)
```

**Conflict safety** is enforced at two layers:

1. `BEGIN IMMEDIATE` transactions prevent concurrent reads from seeing a slot as open while another transaction is writing it
2. Partial unique indexes on `(instructor_id, start_utc) WHERE status = 'active'` and `(aircraft_id, start_utc) WHERE status = 'active'` guarantee uniqueness at the storage layer, catching any race that slips past layer 1

---

## Project structure

```
aerodesk/
├── run.py                        # entry point — server + DB init flags
├── src/hilo_scheduler/
│   ├── api.py                    # HTTP server, routes, request handling
│   ├── scheduling.py             # availability computation, booking logic
│   ├── database.py               # schema, connection pool, transactions
│   ├── time_utils.py             # UTC <-> HST conversion helpers
│   ├── config.py                 # school timezone, lesson duration, cutoff
│   └── seed.py                   # demo instructors, aircraft, students
├── static/
│   ├── index.html                # single-page shell
│   ├── app.js                    # client-side state, rendering, fetch
│   └── styles.css                # design system — dark glass-cockpit theme
└── tests/
    ├── test_scheduling.py        # unit tests: availability, conflicts, policy
    └── test_api.py               # integration test: health -> book -> cancel
```

---

## Key design decisions

**No third-party packages.** The backend runs on the Python standard library. This makes the project portable — no virtual environment, no pip, no lockfile drift. A production deployment would introduce a WSGI server (Gunicorn) and swap SQLite for PostgreSQL.

**`BEGIN IMMEDIATE` over optimistic locking.** SQLite's WAL mode allows concurrent readers, but two concurrent bookings for the same slot would both read "available" before either writes. `BEGIN IMMEDIATE` acquires a write lock at transaction start, serialising concurrent booking attempts. The partial unique index is a backstop, not the primary defence.

**12-hour cancellation is a hard boundary.** The deadline is stored as a UTC timestamp on the booking row at creation time. The API compares it to `datetime.utcnow()` at cancel time — no timezone arithmetic at cancel, no drift.

**Cancelled bookings are never deleted.** The audit trail is immutable. Cancellations set `status = 'cancelled'` and record the reason. Slot availability is re-derived from `WHERE status = 'active'` queries only.

**Fixed school timezone and lesson duration.** Both are constants in `config.py`. A multi-tenant version would make these per-school settings stored alongside each school record.

---

## Out of scope (intentional)

This is a focused correctness demo, not a production SaaS. The following are explicitly not implemented:

- Authentication (student_id is trusted by the API)
- Payments, deposits, or late-cancel fees
- Recurring lesson packages
- Aircraft maintenance events as first-class blocks
- Weather holds or stage-check reservations
- Instructor approvals or waitlists
- Email / push notifications
- Calendar sync (iCal, Google Calendar)
- Admin CRUD screens
- Role-based access control
- Multi-tenant support

---

## PostgreSQL migration path

`supabase_migration.sql` contains a production-ready PostgreSQL schema using exclusion constraints (`tstzrange`) instead of partial unique indexes — more expressive for overlapping interval detection. `create_booking_rpc.sql` wraps the booking logic in a Postgres function for use as a Supabase RPC endpoint.

---

## License

MIT
