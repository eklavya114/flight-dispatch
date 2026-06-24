# Decision Log

## What I understood the real problem to be

The real problem is trust in the schedule. A flight school loses revenue and training continuity when a lesson slot looks available but later turns out not to be, or when a student can take a slot that should have been blocked by instructor, aircraft, or policy constraints. The hard part is not rendering a calendar. The hard part is making the booking decision once, correctly, under concurrent demand.

I treated the customer as both the student trying to self-serve and the school operator who needs the schedule to be authoritative. That led me to prioritize correctness at the booking boundary over breadth of features.

## Scope I chose

I built a small running web app and API that support the core loop: select a student, view real availability for a date, book a one-hour lesson with one instructor and one aircraft, view active bookings, and cancel within policy. The system seeds 3 instructors, 2 aircraft, recurring instructor availability, recurring aircraft availability, and 4 students.

I deliberately did not build authentication, payments, instructor approvals, waitlists, recurring lesson packages, aircraft maintenance events as first-class exceptions, notifications, calendar sync, admin CRUD screens, or no-show prediction. Those are valuable, but they do not prove the hardest scheduling invariant. I would rather submit a small system whose booking path is coherent and tested than a larger system with ambiguous correctness.

## Key technical decisions and tradeoffs

I used Python 3.11 standard library plus SQLite so the reviewer can run the project from a clean checkout without dependency installation. The tradeoff is that this is not the stack I would automatically choose for a production multi-tenant SaaS platform. In production I would expect an API framework, typed request validation, observability, background jobs, and PostgreSQL.

I modeled instructor and aircraft availability as weekly recurring windows and bookings as UTC intervals. The school timezone is fixed to `Pacific/Honolulu`. That keeps the seed scenario clear while avoiding naive local timestamps. A production version would make school timezone configurable per tenant.

I made lessons exactly one hour and required hourly starts. That matches the assessment prompt and lets the database protect active conflicts with simple partial unique indexes on `(resource_id, start_utc)`. The service still runs an overlap query before insert, but if variable lesson lengths were added, I would move the invariant to database-level range/exclusion constraints in PostgreSQL.

I used `BEGIN IMMEDIATE` transactions around booking and cancellation writes. The booking service validates resource existence, availability, future time, hourly boundary, and active conflicts inside the transaction. SQLite partial unique indexes on active instructor, aircraft, and student slots are the final backstop if concurrent requests race after availability is rendered. The concurrency test submits many simultaneous requests for the same instructor-aircraft slot and verifies exactly one winner.

I chose a 12-hour self-service cancellation cutoff. Before the cutoff, the student can cancel and the slot becomes bookable again. Inside the cutoff, self-service cancellation is rejected because the school should handle it as a late cancel with policy or billing implications. Another valid choice would be to allow the cancellation but mark it billable; I chose rejection because it makes the policy boundary explicit in this slice.

## Tests I wrote and why

The tests cover real availability generation from seeded instructor and aircraft windows, successful booking, resource removal after booking, instructor conflict, aircraft conflict, student conflict, concurrent race behavior, valid cancellation, late cancellation rejection, invalid outside-availability booking, non-hour-boundary rejection, and a smoke test through the HTTP API. These are the cases I expect a reviewer to care about because they exercise the actual scheduling invariants rather than only the happy path.

## Where it breaks or is incomplete

The app has no authentication, so `student_id` is trusted by the API. The UI is intentionally simple and not optimized for large calendars. Availability exceptions such as aircraft maintenance, instructor PTO, weather holds, and stage-check reservations are not first-class records. Payments, late-cancel fees, reminders, and audit reporting are not implemented. There is no tenant model, no role model, and no production logging beyond basic server behavior.

SQLite is acceptable for this demo and enforces the important invariant, but it is not the database design I would choose for a scaled multi-instance production deployment. With another week I would move persistence to PostgreSQL, use exclusion constraints for time ranges, add authenticated roles, add one-off availability exceptions, add a staff override workflow for late cancellations, add reminder/confirmation notifications, and add an admin view that explains why a slot is unavailable.

## AI co-development notes

This project is structured so the important engineering choices are visible in code and tests. AI was useful for scaffolding and for quickly exploring edge cases, but the decisions I would defend in a walkthrough are the scoped invariant, the transaction boundary, the database constraints, and the cancellation policy. The reviewer should be able to challenge the tradeoffs above and trace each answer back to a specific test or implementation choice.
