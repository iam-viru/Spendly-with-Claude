# Spec: Date Filter for Profile Page

## Overview

Add a date-range filter to the `/profile` page so users can narrow the spending summary (total spent, category breakdown, and recent transactions) to a specific time window. The filter is submitted as a GET request with query parameters — no new routes required. Three preset shortcuts (This Month, Last 3 Months, This Year) plus a custom date-range picker give users quick access to the most common views. All existing queries gain a `WHERE date BETWEEN ? AND ?` clause; the unfiltered all-time view remains the default when no parameters are present.

## Depends on

- Step 01: Database Setup (`expenses` table with `date`, `amount`, `category`, `user_id` columns)
- Step 02: Registration (users must exist)
- Step 03: Login and Logout (`session["user_id"]` must be set)
- Step 04: Profile Page Design (profile template and route exist)
- Step 05: Backend Routes for Profile Page (`total_spent`, `categories`, `recent` already wired up)

## Routes

- `GET /profile?from=YYYY-MM-DD&to=YYYY-MM-DD` — existing route, extended to accept optional `from` and `to` query params — logged-in only

No new routes.

## Database changes

No database changes. The `expenses.date` column (TEXT, `YYYY-MM-DD`) already supports range comparisons via SQL `BETWEEN`.

## Templates

- **Modify:** `templates/profile.html`
  - Add a filter bar above the spending summary with:
    - Three preset buttons: "This Month", "Last 3 Months", "This Year" — each links to `/profile?from=...&to=...`
    - A mini form with two `<input type="date">` fields (`from`, `to`) and a Submit button
    - An "All time" link that clears the filter (`/profile` with no params)
  - Show an active-filter label ("Showing: Apr 1 – Apr 30 2026") when a filter is applied
  - Pass `from_date` and `to_date` back into the template so preset buttons can highlight the active one

## Files to change

- `app.py`
  - In the `profile()` view, read `request.args.get("from")` and `request.args.get("to")`
  - Validate both are either absent or match `YYYY-MM-DD` format; silently ignore malformed values (treat as absent)
  - If both are present, add `AND date BETWEEN ? AND ?` to all three spending queries (`total_spent`, `categories`, `recent`)
  - Remove the `LIMIT 5` on `recent` when a date filter is active (show all matching transactions)
  - Pass `from_date` and `to_date` (or `None`) to `render_template`

- `templates/profile.html`
  - Add the filter bar UI described above

- `static/css/style.css`
  - Add styles for `.filter-bar`, `.filter-presets`, `.filter-preset-btn`, `.filter-preset-btn.active`, `.filter-custom`, `.filter-label`
  - Use CSS variables only — no hardcoded hex values

## Files to create

None.

## New dependencies

No new dependencies.

## Rules for implementation

- No SQLAlchemy or ORMs — raw `sqlite3` via `get_db()` only
- Parameterised queries only — never use string formatting in SQL
- Passwords hashed with werkzeug (no changes needed here)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Silently discard malformed date params — never crash on bad query-string input
- Guard division by zero: if `total_spent == 0` within the filtered range, `pct = 0` for all categories
- Do not re-validate auth inside the filter logic — the existing auth guard at the top of the route handles this
- `from` and `to` are inclusive bounds: `BETWEEN from_date AND to_date`

## Definition of done

- [ ] Visiting `/profile` with no params shows the all-time spending summary (existing behaviour unchanged)
- [ ] Visiting `/profile?from=2026-04-01&to=2026-04-30` shows only April expenses
- [ ] "This Month" preset link produces the correct `from`/`to` for the current month
- [ ] "Last 3 Months" preset link produces the correct `from`/`to` for the preceding 3 months
- [ ] "This Year" preset link produces the correct `from`/`to` for the current calendar year
- [ ] The custom date-range form submits correctly and filters results
- [ ] An active-filter label is shown when `from`/`to` params are present
- [ ] Malformed date params (`?from=bad&to=also-bad`) do not crash the route — page loads as all-time
- [ ] A filtered view with zero matching expenses shows "No expenses yet." and a total of $0.00
- [ ] The app starts without errors (`python app.py`)
