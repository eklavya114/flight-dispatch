# One-Page Memo: Hilo Flight Scheduler

Hilo Flight Scheduler is a small, runnable flight school booking slice that proves core scheduling and cancellation policy behavior without becoming a full enterprise platform.

## What this project does

- Models students, instructors, aircraft, weekly instructor availability, weekly aircraft availability, and one-hour lesson bookings.
- Exposes a browser-based UI for selecting a student and date, viewing available instructor-aircraft combinations, booking a lesson, and cancelling eligible bookings.
- Provides a JSON API for health checks, students, instructors, aircraft, availability, bookings, and cancellations.
- Uses a SQLite database with transactional booking logic plus database constraints to prevent double-booking.
- Enforces a deliberate cancellation policy: students may self-cancel only until 12 hours before lesson start.

## Scope and implementation

The app is intentionally narrow. It focuses on:

- hourly lessons that start on the hour,
- instructor and aircraft availability windows expressed as weekly recurring schedules,
- UTC-backed bookings with local timezone display using `Pacific/Honolulu`,
- active booking conflict protection through both application overlap checks and partial unique indexes,
- a single booking status model with `active` and `cancelled` states,
- seeded demo data for 3 instructors, 2 aircraft, and 4 students.

It does not attempt advanced features such as machine-learning prediction, dynamic deposits, waitlist markets, payment processing, or complex instructor scoring.

## Key behaviors

- Availability is computed from instructor and aircraft weekly windows, active bookings, and student conflicts.
- Lessons can only be booked for future top-of-hour slots.
- Bookings are rejected if the instructor or aircraft is unavailable or already reserved.
- Cancellations are allowed only if the request occurs at least 12 hours before the lesson start.
- Cancelled bookings are retained in the database for auditability.

## Why this matters

The project demonstrates the scheduling heart of a flight school system: matching students, instructors, and aircraft while preserving strict conflict and cancellation rules. This makes it a solid foundation for later work on recovery workflows, confirmations, waitlisting, or richer policy automation.

## Running and validation

- `python run.py` starts the local server.
- `python run.py --reset-db` recreates the database.
- `python run.py --init-db` initializes the database without starting the server.
- `python -m unittest discover -s tests -v` runs the test suite.

The UI is available at `http://127.0.0.1:8080` after startup.
