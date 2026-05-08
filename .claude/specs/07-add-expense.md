# Spec: Add Expense

## Overview
This feature lets a logged-in user submit a new expense through a form at `/expenses/add`. It replaces the placeholder route with a working GET (render form) + POST (save to database) handler. This is the first write path for expense data and the core action that makes Spendly useful day-to-day.

## Depends on
- Step 01 — Database Setup (expenses table must exist)
- Step 03 — Login and Logout (session-based auth must be working)

## Routes
- `GET /expenses/add` — render the add-expense form — logged-in only
- `POST /expenses/add` — validate and insert a new expense row, redirect to profile on success — logged-in only

## Database changes
No database changes. The `expenses` table already exists with the required columns: `id`, `user_id`, `amount`, `category`, `date`, `description`, `created_at`.

## Templates
- **Create:** `templates/add_expense.html` — form with fields: amount, category (dropdown), date (date input defaulting to today), description (optional textarea). Shows inline validation errors on re-render.
- **Modify:** `templates/base.html` — ensure the navbar has a visible "Add Expense" link pointing to `/expenses/add` for logged-in users (if not already present).

## Files to change
- `app.py` — replace the placeholder `add_expense` route with GET + POST implementation

## Files to create
- `templates/add_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (not applicable here, but keep the import)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Redirect to `/profile` after a successful POST
- Re-render the form with the user's input preserved on validation failure
- `amount` must be a positive number; reject zero or negative values
- `date` must be a valid date; default the input to today's date (`date.today().isoformat()`)
- `category` must be one of the fixed allowed values: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- `description` is optional (max 200 characters if provided)
- If the user is not logged in, redirect to `/login`

## Definition of done
- [ ] Visiting `/expenses/add` when logged out redirects to `/login`
- [ ] Visiting `/expenses/add` when logged in renders a form with amount, category, date, and description fields
- [ ] The date field defaults to today's date
- [ ] Submitting the form with valid data inserts a row into the `expenses` table and redirects to `/profile`
- [ ] The new expense is visible on the profile page after submission
- [ ] Submitting with a missing or zero amount re-renders the form with an error message and preserves other field values
- [ ] Submitting with a missing category re-renders the form with an error
- [ ] Submitting with a missing date re-renders the form with an error
- [ ] The navbar shows an "Add Expense" link for logged-in users
