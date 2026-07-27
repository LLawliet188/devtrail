"""DevTrail - a small personal task manager for my own development work.

Prototype for the DLBCSPSE01 project report. Single user, runs locally.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

from flask import Flask, g, redirect, render_template, request, url_for, flash

APP_DIR = Path(__file__).parent
DB_PATH = APP_DIR / "devtrail.db"

# tasks that were not touched for this many days count as stale
STALE_DAYS = 7
# how many tasks I allow myself to have Active at the same time
WIP_LIMIT = 3

app = Flask(__name__)
app.secret_key = "devtrail-local-prototype"  # only used for flash messages

STATUSES = ["backlog", "active", "paused", "done"]


# ---------------------------------------------------------------- database

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = sqlite3.connect(DB_PATH)
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS contexts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL DEFAULT 'project',   -- 'project' or 'course'
            color TEXT NOT NULL DEFAULT '#4a6fa5'
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            notes TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'backlog',
            priority INTEGER NOT NULL DEFAULT 2,    -- 1 high, 2 normal, 3 low
            context_id INTEGER REFERENCES contexts(id) ON DELETE SET NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            due_date TEXT
        );

        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            branch TEXT DEFAULT '',
            open_files TEXT DEFAULT '',
            last_commands TEXT DEFAULT '',
            next_step TEXT DEFAULT '',
            created_at TEXT NOT NULL
        );
        """
    )
    db.commit()
    db.close()


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def touch(db, task_id):
    db.execute("UPDATE tasks SET updated_at = ? WHERE id = ?", (now(), task_id))


def latest_snapshot(db, task_id):
    return db.execute(
        "SELECT * FROM snapshots WHERE task_id = ? ORDER BY id DESC LIMIT 1",
        (task_id,),
    ).fetchone()


def stale_cutoff():
    return (datetime.now() - timedelta(days=STALE_DAYS)).strftime("%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------- views

@app.route("/")
def board():
    db = get_db()
    ctx_filter = request.args.get("context", type=int)

    query = "SELECT t.*, c.name AS ctx_name, c.color AS ctx_color, c.kind AS ctx_kind " \
            "FROM tasks t LEFT JOIN contexts c ON t.context_id = c.id"
    args = []
    if ctx_filter:
        query += " WHERE t.context_id = ?"
        args.append(ctx_filter)
    query += " ORDER BY t.priority, t.updated_at DESC"

    tasks = db.execute(query, args).fetchall()
    columns = {s: [t for t in tasks if t["status"] == s] for s in STATUSES}

    contexts = db.execute("SELECT * FROM contexts ORDER BY kind, name").fetchall()
    stale_count = db.execute(
        "SELECT COUNT(*) FROM tasks WHERE status IN ('backlog','paused') AND updated_at < ?",
        (stale_cutoff(),),
    ).fetchone()[0]

    # resume card for the most recently paused task
    resume = db.execute(
        "SELECT t.id, t.title FROM tasks t WHERE t.status = 'paused' "
        "ORDER BY t.updated_at DESC LIMIT 1"
    ).fetchone()
    resume_snap = latest_snapshot(db, resume["id"]) if resume else None

    return render_template(
        "board.html",
        columns=columns,
        contexts=contexts,
        ctx_filter=ctx_filter,
        stale_count=stale_count,
        resume=resume,
        resume_snap=resume_snap,
        wip_limit=WIP_LIMIT,
        active_count=len(columns["active"]),
    )


@app.route("/task/new", methods=["GET", "POST"])
def new_task():
    db = get_db()
    if request.method == "POST":
        title = request.form["title"].strip()
        if not title:
            flash("A task needs a title.")
            return redirect(url_for("new_task"))
        db.execute(
            "INSERT INTO tasks (title, notes, priority, context_id, due_date, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                title,
                request.form.get("notes", "").strip(),
                request.form.get("priority", 2, type=int),
                request.form.get("context_id") or None,
                request.form.get("due_date") or None,
                now(),
                now(),
            ),
        )
        db.commit()
        flash("Task created.")
        return redirect(url_for("board"))
    contexts = db.execute("SELECT * FROM contexts ORDER BY kind, name").fetchall()
    return render_template("task_form.html", contexts=contexts, task=None)


@app.route("/task/<int:task_id>")
def task_detail(task_id):
    db = get_db()
    task = db.execute(
        "SELECT t.*, c.name AS ctx_name, c.color AS ctx_color FROM tasks t "
        "LEFT JOIN contexts c ON t.context_id = c.id WHERE t.id = ?",
        (task_id,),
    ).fetchone()
    if task is None:
        flash("Task not found.")
        return redirect(url_for("board"))
    snapshots = db.execute(
        "SELECT * FROM snapshots WHERE task_id = ? ORDER BY id DESC", (task_id,)
    ).fetchall()
    return render_template("task_detail.html", task=task, snapshots=snapshots)


@app.route("/task/<int:task_id>/status", methods=["POST"])
def change_status(task_id):
    db = get_db()
    new_status = request.form["status"]
    if new_status not in STATUSES:
        flash("Unknown status.")
        return redirect(url_for("task_detail", task_id=task_id))

    # WIP limit check: warn me instead of silently letting the board fill up
    if new_status == "active":
        active = db.execute(
            "SELECT COUNT(*) FROM tasks WHERE status = 'active' AND id != ?", (task_id,)
        ).fetchone()[0]
        if active >= WIP_LIMIT:
            flash(f"WIP limit reached ({WIP_LIMIT} active tasks). Pause or finish one first.")
            return redirect(request.referrer or url_for("board"))

    db.execute("UPDATE tasks SET status = ? WHERE id = ?", (new_status, task_id))
    touch(db, task_id)
    db.commit()
    return redirect(request.referrer or url_for("board"))


@app.route("/task/<int:task_id>/pause", methods=["GET", "POST"])
def pause_task(task_id):
    """Pause a task and record a context snapshot so I can resume it later."""
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if task is None:
        flash("Task not found.")
        return redirect(url_for("board"))

    if request.method == "POST":
        db.execute(
            "INSERT INTO snapshots (task_id, branch, open_files, last_commands, next_step, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                task_id,
                request.form.get("branch", "").strip(),
                request.form.get("open_files", "").strip(),
                request.form.get("last_commands", "").strip(),
                request.form.get("next_step", "").strip(),
                now(),
            ),
        )
        db.execute("UPDATE tasks SET status = 'paused' WHERE id = ?", (task_id,))
        touch(db, task_id)
        db.commit()
        flash("Snapshot saved, task paused.")
        return redirect(url_for("board"))

    return render_template("pause_form.html", task=task)


@app.route("/task/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id):
    db = get_db()
    task = db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if task is None:
        flash("Task not found.")
        return redirect(url_for("board"))
    if request.method == "POST":
        title = request.form["title"].strip()
        if not title:
            flash("A task needs a title.")
            return redirect(url_for("edit_task", task_id=task_id))
        db.execute(
            "UPDATE tasks SET title = ?, notes = ?, priority = ?, context_id = ?, due_date = ? WHERE id = ?",
            (
                title,
                request.form.get("notes", "").strip(),
                request.form.get("priority", 2, type=int),
                request.form.get("context_id") or None,
                request.form.get("due_date") or None,
                task_id,
            ),
        )
        touch(db, task_id)
        db.commit()
        flash("Task updated.")
        return redirect(url_for("task_detail", task_id=task_id))
    contexts = db.execute("SELECT * FROM contexts ORDER BY kind, name").fetchall()
    return render_template("task_form.html", contexts=contexts, task=task)


@app.route("/task/<int:task_id>/delete", methods=["POST"])
def delete_task(task_id):
    db = get_db()
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()
    flash("Task deleted.")
    return redirect(url_for("board"))


@app.route("/review")
def review():
    """The revival queue: everything I have not touched in a while."""
    db = get_db()
    tasks = db.execute(
        "SELECT t.*, c.name AS ctx_name, c.color AS ctx_color FROM tasks t "
        "LEFT JOIN contexts c ON t.context_id = c.id "
        "WHERE t.status IN ('backlog','paused') AND t.updated_at < ? "
        "ORDER BY t.updated_at",
        (stale_cutoff(),),
    ).fetchall()
    return render_template("review.html", tasks=tasks, stale_days=STALE_DAYS)


@app.route("/contexts", methods=["GET", "POST"])
def contexts_view():
    db = get_db()
    if request.method == "POST":
        name = request.form["name"].strip()
        if name:
            try:
                db.execute(
                    "INSERT INTO contexts (name, kind, color) VALUES (?, ?, ?)",
                    (name, request.form.get("kind", "project"),
                     request.form.get("color", "#4a6fa5")),
                )
                db.commit()
            except sqlite3.IntegrityError:
                flash("A context with that name already exists.")
        return redirect(url_for("contexts_view"))
    rows = db.execute(
        "SELECT c.*, COUNT(t.id) AS task_count FROM contexts c "
        "LEFT JOIN tasks t ON t.context_id = c.id GROUP BY c.id ORDER BY c.kind, c.name"
    ).fetchall()
    return render_template("contexts.html", contexts=rows)


if __name__ == "__main__":
    init_db()
    app.run(debug=True, port=5001)
