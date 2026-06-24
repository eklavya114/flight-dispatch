import sqlite3, datetime, sys
if len(sys.argv) < 2:
    print("Usage: python force_cancel.py <booking_id> [booking_id ...]")
    raise SystemExit(1)
db = "data/hilo_scheduler.sqlite3"
now = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
conn = sqlite3.connect(db)
cur = conn.cursor()
for a in sys.argv[1:]:
    bid = int(a)
    cur.execute(
        "UPDATE bookings SET status='cancelled', cancelled_at_utc=?, cancellation_reason=?, cancellation_policy_result='admin_cancelled' WHERE id=?",
        (now, 'admin_override', bid)
    )
    print("booking", bid, "marked cancelled")
conn.commit()
conn.close()
