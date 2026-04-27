# Spec: Profile Page Design

## Overview

Implement the `/profile` route so logged-in users can view their account information. The profile page displays the user's name, email, and account creation date pulled from the database. It also acts as the first protected route — unauthenticated users who visit `/profile` are redirected to `/login`. This step introduces the auth-guard pattern that all future protected routes (expenses, dashboard) will reuse.

## Depends on

- Step 01: Database Setup (`users` table with `name`, `email`, `created_at` columns)
- Step 02: Registration (users must exist in the database)
- Step 03: Login and Logout (session must be set; `session["user_id"]` is the auth signal)

## Routes

- `GET /profile` — displays the logged-in user's profile — logged-in only (redirect to `/login` if no session)

## Database changes

No database changes. The existing `users` table already has all required columns: `id`, `name`, `email`, `created_at`.

## Templates

- **Create:** `templates/profile.html`
  - Extends `base.html`
  - Displays: user's name, email address, and member-since date (formatted from `created_at`)
  - Uses the existing CSS card/container patterns from `style.css`

- **Modify:** `templates/base.html`
  - Add a "Profile" link in the logged-in nav (alongside the existing "Sign out" button)

## Files to change

- `app.py`
  - Replace the `/profile` placeholder string response with a real handler
  - Query the `users` table by `session["user_id"]`
  - If no session → `redirect(url_for("login"))`
  - Pass the user row to `profile.html`

- `templates/base.html`
  - Add `<a href="{{ url_for('profile') }}">Profile</a>` inside the logged-in `{% if session.get('user_id') %}` nav block

- `static/css/style.css`
  - Add styles for the profile page layout (`.profile-section`, `.profile-card`, `.profile-field`, `.profile-label`, `.profile-value`)
  - Use only existing CSS variables — no hardcoded hex values

## Files to create

- `templates/profile.html`

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never use string formatting in SQL
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Auth guard: if `session.get("user_id")` is falsy, redirect to `/login` before any DB query
- Format `created_at` in the template using Jinja2's string slice or pass a pre-formatted string from the route — keep it human readable (e.g. "April 2026")
- Do not expose `password_hash` or `id` in the template context — pass only `name`, `email`, `created_at`

## Definition of done

- [ ] Visiting `/profile` while logged in shows the user's name and email
- [ ] The profile page shows the account creation date in a human-readable format
- [ ] Visiting `/profile` while **not** logged in redirects to `/login` (302)
- [ ] The navbar shows a "Profile" link when logged in
- [ ] Clicking "Profile" in the navbar navigates to `/profile`
- [ ] The page is styled using only CSS variables — no hardcoded colours
- [ ] The app starts without errors (`python app.py`)
