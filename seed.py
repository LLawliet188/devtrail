"""Fill the database with my actual current workload so the prototype
has something realistic to show."""

import sqlite3
from datetime import datetime, timedelta

from app import DB_PATH, init_db


def days_ago(n, hours=0):
    return (datetime.now() - timedelta(days=n, hours=hours)).strftime("%Y-%m-%d %H:%M:%S")


init_db()
db = sqlite3.connect(DB_PATH)
db.execute("PRAGMA foreign_keys = ON")
db.execute("DELETE FROM snapshots")
db.execute("DELETE FROM tasks")
db.execute("DELETE FROM contexts")

contexts = [
    ("Wanderlust", "project", "#2f6fed"),
    ("SpendLens", "project", "#12805c"),
    ("Aegis Scanner", "project", "#7048e8"),
    ("DLBCSPSE01 Software Eng.", "course", "#d9480f"),
    ("DLBDSPBDM01 Data Mart", "course", "#c2255c"),
]
for name, kind, color in contexts:
    db.execute("INSERT INTO contexts (name, kind, color) VALUES (?, ?, ?)", (name, kind, color))

ctx = {row[1]: row[0] for row in db.execute("SELECT id, name FROM contexts")}

tasks = [
    # title, notes, status, prio, context, created, updated, due
    ("Fix trip search pagination", "Second page repeats the first three results. Probably the offset calc in the API route.",
     "active", 1, "Wanderlust", days_ago(3), days_ago(0, 2), None),
    ("Write chapter 3 system design", "Subsystem decomposition + deployment diagram still missing.",
     "active", 1, "DLBCSPSE01 Software Eng.", days_ago(5), days_ago(0, 5), "2026-08-02"),
    ("CSV import for bank statements", "Sparkasse CSV has a weird delimiter. Need a small parser test set.",
     "paused", 2, "SpendLens", days_ago(9), days_ago(1), None),
    ("Rate limiting for scan endpoint", "Look at flask-limiter vs writing a tiny token bucket myself.",
     "backlog", 2, "Aegis Scanner", days_ago(12), days_ago(12), None),
    ("Map view for saved trips", "Leaflet or MapLibre? Check bundle size first.",
     "backlog", 3, "Wanderlust", days_ago(16), days_ago(16), None),
    ("Monthly budget summary widget", "",
     "backlog", 3, "SpendLens", days_ago(21), days_ago(21), None),
    ("Review phase 2 tutor feedback", "Go through the feedback PDF and note what applies to phase 3.",
     "backlog", 2, "DLBDSPBDM01 Data Mart", days_ago(10), days_ago(10), "2026-07-30"),
    ("Set up e2e tests with Playwright", "At least the booking happy path.",
     "done", 2, "Wanderlust", days_ago(14), days_ago(2), None),
    ("Dockerfile for the API", "Multi-stage build, final image ~120MB now.",
     "done", 2, "Aegis Scanner", days_ago(20), days_ago(6), None),
]
for title, notes, status, prio, cname, created, updated, due in tasks:
    db.execute(
        "INSERT INTO tasks (title, notes, status, priority, context_id, created_at, updated_at, due_date)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (title, notes, status, prio, ctx[cname], created, updated, due),
    )

# snapshot for the paused CSV import task
task_id = db.execute("SELECT id FROM tasks WHERE title LIKE 'CSV import%'").fetchone()[0]
db.execute(
    "INSERT INTO snapshots (task_id, branch, open_files, last_commands, next_step, created_at)"
    " VALUES (?, ?, ?, ?, ?, ?)",
    (
        task_id,
        "feature/csv-import",
        "importers/sparkasse.py, tests/test_sparkasse.py",
        "pytest tests/test_sparkasse.py -k delimiter",
        "Handle the quoted semicolon case in row 14 of the sample file, then wire the importer into the upload view.",
        days_ago(1),
    ),
)

db.commit()
db.close()
print("seeded.")
