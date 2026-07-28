# DevTrail

A small personal task manager for my own development work. I built it because the
problem with juggling several projects was never the tasks themselves, it was
switching between them: coming back to a bug three days later, I would spend the
first twenty minutes working out which branch I was on and what I had been about
to try.

DevTrail is a local, single-user web app. Nothing leaves the laptop, there is no
account, and all data lives in one SQLite file.

## What makes it different from a normal to-do list

- **Context snapshots.** Pausing a task is a first-class action. When you pause,
  you write down the git branch, the open files, the last commands and — the
  important one — the next step. That snapshot is kept.
- **Resume card.** The board greets you with the latest snapshot of the most
  recently paused task, so getting back in takes seconds instead of minutes.
- **A WIP limit that actually says no.** Three active tasks maximum. Trying to
  start a fourth is refused, not just discouraged.
- **A review queue.** Backlog and paused tasks untouched for more than seven days
  surface in one place, where you either revive them or drop them, so the
  backlog cannot quietly rot.
- **Contexts.** Tasks are grouped by project or university course, and the board
  can be filtered by them.

## Running it

```bash
pip install -r requirements.txt
python app.py
```

Then open <http://localhost:5001>.

To fill the board with sample data (this resets the database):

```bash
python seed.py
```

## Deploying it

`app.py` is written for localhost. `wsgi.py` wraps it for a host without
changing that file: it takes the secret key from the environment, puts the
database wherever `DEVTRAIL_DB` points, creates the schema on first boot and
loads the sample data if the database is still empty.

```bash
gunicorn wsgi:application --bind 0.0.0.0:$PORT --workers 1 --threads 4
```

One worker on purpose — the database is SQLite, so several processes writing
to the same file would only fight each other.

| Variable       | Default              | What it does                          |
| -------------- | -------------------- | ------------------------------------- |
| `SECRET_KEY`   | the local dev value  | Signs the session cookie              |
| `DEVTRAIL_DB`  | `./devtrail.db`      | Where the database file lives         |
| `DEVTRAIL_SEED`| `1`                  | Load sample data into an empty database |
| `PORT`         | `8000`               | Port to bind                          |

There is a `Dockerfile`, a `render.yaml` blueprint and a `Procfile`, so most
platforms will pick this up on their own. With Docker:

```bash
docker build -t devtrail .
docker run -p 8000:8000 -e SECRET_KEY=something-random devtrail
```

**Before you put this on the public internet, read this.** DevTrail has no
login, no accounts and no permissions — that was a deliberate decision for a
tool that only ever ran on my own laptop behind the OS login. Hosted at a
public URL, anyone who finds it can read, edit and delete everything. Treat a
deployed instance as a throwaway demo with sample data, not as somewhere to
keep real work. On a free plan with no persistent disk the database also lives
on the container filesystem, so it resets on every restart and re-seeds itself.

## How it is put together

Flask with Jinja2 templates and plain CSS, SQLite through the standard `sqlite3`
module. No build step, no ORM, no external services.

| Path               | What it holds                                          |
| ------------------ | ------------------------------------------------------ |
| `app.py`           | Views, WIP policy, staleness rule, all database access  |
| `seed.py`          | Sample contexts, tasks and one snapshot                 |
| `wsgi.py`          | Production entry point (env config, first-boot setup)   |
| `templates/`       | Board, task detail, forms, review queue, contexts       |
| `static/style.css` | Styling                                                 |

Three tables: `contexts`, `tasks` and `snapshots`. Deleting a task cascades to
its snapshots; deleting a context leaves its tasks alone and just unlinks them.

## Not done yet

- Detecting the current git branch automatically instead of typing it in. This is
  the one that matters most: the snapshot is written at the moment of
  interruption, which is exactly when you are least inclined to type carefully.
- Full-text search across tasks, notes and snapshots.
- Automated tests. The WIP limit and the failure cases were checked by hand.

## Context

Written as the prototype for a university software engineering project, where it
was specified with UML and then implemented. The code here is my own work; the
accompanying coursework document is not part of this repository.
