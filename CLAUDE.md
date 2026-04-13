# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the development server (port 5001)
python app.py

# Run tests
pytest

# Run a single test file
pytest tests/test_auth.py

# Run a single test
pytest tests/test_auth.py::test_login
```

Set up a virtual environment before running:
```bash
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

## Architecture

**Spendly** is a monolithic Flask app (server-side rendered, no REST API separation).

- `app.py` — Single entry point. All route definitions live here. Runs on port 5001 with debug mode.
- `database/db.py` — SQLite helpers: `get_db()`, `init_db()`, `seed_db()`. Uses raw SQL (no ORM). The DB file `expense_tracker.db` is gitignored.
- `templates/` — Jinja2 templates. All pages extend `base.html`, which provides the navbar, footer, and script injection blocks.
- `static/css/style.css` — Single stylesheet using CSS custom properties. Design tokens: `--ink`, `--accent` (teal), `--accent-2` (orange), `--paper` (background). Typography: DM Serif Display (headings) + DM Sans (body) from Google Fonts.
- `static/js/main.js` — Vanilla JS for client-side interactions (currently: YouTube modal on landing page).

## Route Status

Routes are being implemented incrementally. Current state:

| Route | Status |
|---|---|
| `/`, `/login`, `/register`, `/terms`, `/privacy` | Implemented (GET only) |
| `/logout`, `/profile` | Placeholder |
| `/expenses/add`, `/expenses/<id>/edit`, `/expenses/<id>/delete` | Placeholder |

POST handlers for `/login` and `/register` are not yet implemented — form submissions are not processed.

## Database

`database/db.py` is a placeholder. When implementing:
- `get_db()` should return a `sqlite3.connect()` connection with `row_factory = sqlite3.Row` and `PRAGMA foreign_keys = ON`
- `init_db()` creates tables with `CREATE TABLE IF NOT EXISTS`
- `seed_db()` inserts sample development data
- The app uses Flask sessions for auth (not yet implemented)
