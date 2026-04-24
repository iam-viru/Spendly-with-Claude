# Spec: Registration

## Overview

Implement the POST handler for `/register` so new users can create a Spendly account. This step makes the registration form functional: it validates the submitted fields, hashes the password, inserts the new user into the `users` table, starts a Flask session, and redirects to a post-registration destination. It also wires up `app.secret_key` so sessions work. This is the first user-facing auth step and is a prerequisite for login, logout, and all protected routes.

## Depends on

- Step 01: Database Setup (users table must exist; `get_db()` must be functional)

## Routes

- `POST /register` — processes the registration form — public

The existing `GET /register` route remains unchanged.

## Database changes

No new tables or columns. The existing `users` table is sufficient:

```
users (id, name, email, password_hash, created_at)
```

## Templates

- **Modify:** `templates/register.html`
  - Re-render the form with the submitted `name` and `email` pre-filled when there is an error (so the user does not have to retype)
  - The `{% if error %}` block is already present — no structural change needed, just ensure the route passes `error=` and `name=`/`email=` values back on failure

## Files to change

- `app.py`
  - Add `secret_key` to the Flask app config
  - Import `request`, `redirect`, `url_for`, `session` from `flask`
  - Import `generate_password_hash` from `werkzeug.security`
  - Add `POST` method to the `/register` route decorator
  - Implement the POST handler logic inside the `register()` view function

## Files to create

None.

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never use string formatting in SQL
- Passwords hashed with `werkzeug.security.generate_password_hash`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- `app.secret_key` must be set before any session usage; use a hard-coded dev string for now (e.g. `"spendly-dev-secret"`) — a comment should note it must be replaced from an env var in production
- Validation order:
  1. All fields present and non-empty
  2. Password is at least 8 characters
  3. Email is not already registered (catch `sqlite3.IntegrityError` on insert)
- On any validation failure: re-render `register.html` with `error=<message>`, `name=`, and `email=` so the user does not lose their input
- On success: set `session["user_id"]` and `session["user_name"]`, then redirect to `/` (landing page — the dashboard route does not exist yet)
- Do not use Flask-Login or any auth extension

## Definition of done

- [ ] Submitting the form with all valid fields creates a new row in `users`
- [ ] The stored password is a hash, not plaintext
- [ ] After successful registration, `session["user_id"]` is set
- [ ] After successful registration, the browser is redirected (302) to `/`
- [ ] Submitting with an empty name, email, or password re-renders `/register` with an error message
- [ ] Submitting a password shorter than 8 characters re-renders `/register` with an error message
- [ ] Submitting a duplicate email re-renders `/register` with an error message (no crash)
- [ ] On error, the name and email fields are pre-filled with the values the user typed
- [ ] The app starts without errors (`python app.py`)
