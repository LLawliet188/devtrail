"""Production entry point.

`app.py` is written for running DevTrail locally on my own laptop. This module
wraps it for a hosted environment without changing that file: it moves the
database to a writable location, takes the secret key from the environment,
creates the schema on first boot and puts the sample data in if the database
is still empty.

Run with:  gunicorn wsgi:application
"""

import os
import sqlite3
from pathlib import Path

import app as devtrail

# Where to keep the database. On a host with a mounted disk, point
# DEVTRAIL_DB at it; otherwise it lands next to the code and is lost on
# redeploy, which is fine for a demo instance.
devtrail.DB_PATH = Path(os.environ.get("DEVTRAIL_DB", devtrail.DB_PATH))
devtrail.DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# The hard-coded key in app.py is only good enough for localhost.
devtrail.app.secret_key = os.environ.get("SECRET_KEY", devtrail.app.secret_key)

devtrail.init_db()


def _is_empty():
    con = sqlite3.connect(devtrail.DB_PATH)
    try:
        return con.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0
    finally:
        con.close()


# A brand new deployment would otherwise show an empty board, which says
# nothing about what the app does. seed.py does its work on import, and it
# reads app.DB_PATH, which was already redirected above.
if os.environ.get("DEVTRAIL_SEED", "1") == "1" and _is_empty():
    import seed  # noqa: F401

application = devtrail.app

if __name__ == "__main__":
    application.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
