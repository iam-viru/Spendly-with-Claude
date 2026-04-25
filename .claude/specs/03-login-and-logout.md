# Spec: Login and Logout

## Overview

Implement the POST handler for `/login` so existing users can sign in to Spendly, and replace the `/logout` placeholder with a working handler that clears the session. After this step, users can complete a full auth cycle: register, log in, and log out. It also sets the foundation for protecting routes in later steps using `session["user_id"]`.

## Depends on

- Step 01: Database Setup (`users` table and `get_db()` must be functional)
- Step 02: Registration (users must exist in the database to log in)

## Routes

- `POST /login` — validates credentials, starts session, redirects on success — public
- `GET /logout` — clears the session and redirects to `/` — public (safe to call even if not logged in)

The existing `GET /login` route remains unchanged.

## Database changes

No database changes. The existing `users` table already has the `email` and `password_hash` columns needed for login.

## Templates

- **Modify:** `templates/login.html`
  - Pre-fill the `email` input with the submitted value on error (so the user does not have to retype)
  - The `{% if error %}` block is already present — no structural change needed, just ensure the route passes `error=` and `email=` values back on failure

## Files to change

- `app.py`
  - Import `check_password_hash` from `werkzeug.security`
  - Add `POST` method to the `/login` route decorator
  - Implement the POST handler logic inside the `login()` view function
  - Replace the `/logout` placeholder string response with a real handler that clears the session and redirects

## Files to create

None.

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never use string formatting in SQL
- Passwords verified with `werkzeug.security.check_password_hash`
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Login validation order:
  1. Both fields present and non-empty
  2. Look up user by email — if not found, render error ("Invalid email or password")
  3. Check password hash — if mismatch, render the same generic error ("Invalid email or password")
  - Use a single generic error for both missing-user and wrong-password to avoid user enumeration
- On login success: set `session["user_id"]` and `session["user_name"]`, then redirect to `/`
- On login failure: re-render `login.html` with `error=<message>` and `email=<submitted_email>` so the user does not lose their email
- Logout must call `session.clear()` (not `session.pop()` on individual keys) and redirect to `/`
- Do not use Flask-Login or any auth extension

## Definition of done

- [ ] Submitting the login form with a valid email and correct password sets `session["user_id"]` and redirects (302) to `/`
- [ ] After login, `session["user_name"]` matches the name stored in the database
- [ ] Submitting with an incorrect password re-renders `/login` with an error message and does not set a session
- [ ] Submitting with an email that does not exist re-renders `/login` with the same generic error (no crash, no user enumeration)
- [ ] Submitting with an empty email or password re-renders `/login` with an error message
- [ ] On login error, the email field is pre-filled with the value the user typed
- [ ] Visiting `/logout` clears the session and redirects (302) to `/`
- [ ] Visiting `/logout` when already logged out does not crash — it redirects cleanly
- [ ] The app starts without errors (`python app.py`)
