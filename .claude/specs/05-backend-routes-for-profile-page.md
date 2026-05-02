# Spec: Backend Routes for Profile Page

## Overview

Enrich the `/profile` route with spending data so the profile page becomes a useful financial summary, not just a static account card. This step adds three backend queries to the existing profile handler: total amount spent, a per-category breakdown with percentages, and the five most recent transactions. The template already renders these values — this step formalises the backend contract and verifies all data is wired up correctly.

## Depends on

- Step 01: Database Setup (`expenses` table with `user_id`, `amount`, `category`, `date`, `description` columns)
- Step 02: Registration (users must exist)
- Step 03: Login and Logout (`session["user_id"]` must be set)
- Step 04: Profile Page Design (template and route shell already exist)

## Routes

- `GET /profile` — already exists; extend the handler with spending queries — logged-in only

No new routes.

## Database changes

No database changes. The existing `users` and `expenses` tables provide all required data.

## Templates

- **Modify:** `templates/profile.html`
  - Add a spending summary section: total spent, category bars with percentages, recent transactions list
  - All data is passed from the route — no logic in the template beyond iteration and formatting
  - Use `{{ "%.2f"|format(amount) }}` for currency display
  - Show "No expenses yet." empty state when `recent` is empty

## Files to change

- `app.py`
  - In the `profile()` view, after fetching the user row, add:
    1. `total_spent` — `SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?`
    2. `categories` — `SELECT category, SUM(amount) as total FROM expenses WHERE user_id = ? GROUP BY category ORDER BY total DESC` — compute `pct = round(total / total_spent * 100)` in Python; guard against `total_spent == 0`
    3. `recent` — `SELECT amount, category, date, description FROM expenses WHERE user_id = ? ORDER BY date DESC LIMIT 5`
  - Pass all three to `render_template("profile.html", ..., total_spent=total_spent, categories=categories, recent=recent)`

- `templates/profile.html`
  - Add spending summary block below the account info card

- `static/css/style.css`
  - Add styles for `.spend-header`, `.category-bar`, `.category-bar-fill`, `.transaction-row` (only if not already present)
  - Use CSS variables only — no hardcoded hex values

## Files to create

None.

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never use string formatting in SQL
- Passwords hashed with werkzeug (no changes needed here, but do not weaken existing auth)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Guard division by zero: if `total_spent == 0`, set `pct = 0` for all categories
- Do not expose `password_hash` or raw `id` in template context
- Category bar widths must be driven by CSS variable or inline `style="width: {{ cat.pct }}%"` — not JS

## Definition of done

- [ ] Visiting `/profile` while logged in shows the correct total amount spent
- [ ] Category breakdown lists every category the user has spent in, with correct percentages summing to ~100%
- [ ] The five most recent transactions appear in reverse-chronological order
- [ ] A user with no expenses sees a "No expenses yet." message instead of empty sections
- [ ] Division by zero does not crash the route when a user has no expenses
- [ ] Visiting `/profile` while not logged in redirects to `/login` (302) — auth guard unchanged
- [ ] The app starts without errors (`python app.py`)
