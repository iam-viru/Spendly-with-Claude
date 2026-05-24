# Spec: Edit Expense

## Overview
This feature lets a logged-in user edit an existing expense via `/expenses/<id>/edit`. It replaces the GET-only placeholder with a working GET (render prefilled form) + POST (validate and update) handler. The profile page is updated to surface edit links on each transaction row. An ownership check ensures users can only edit their own expenses.

## Depends on
- Step 01 — Database Setup (expenses table must exist)
- Step 03 — Login and Logout (session-based auth must be working)
- Step 07 — Add Expense (establishes the form pattern and EXPENSE_CATEGORIES constant this feature mirrors)

## Routes
- `GET /expenses/<int:id>/edit` — render the edit form prefilled with the existing expense — logged-in only
- `POST /expenses/<int:id>/edit` — validate and update the expense row, redirect to profile on success — logged-in only

## Database changes
No database changes. The `expenses` table already has all required columns.

## Templates
- **Create:** `templates/edit_expense.html` — mirrors `add_expense.html` with all four fields (amount, category, date, description) prefilled from the existing expense. Title and submit button read "Edit Expense" / "Update Expense".
- **Modify:** `templates/profile.html` — add an "Edit" link on each transaction row pointing to `url_for('edit_expense', id=txn.id)`. The profile route query must be updated to include `id` in the selected columns.

## Files to change
- `app.py` — replace the placeholder `edit_expense` route with GET + POST implementation; update the three `recent` queries in `profile()` to include `id` in the SELECT so the template can build edit links
- `templates/profile.html` — add edit links to each `.txn-row`

## Files to create
- `templates/edit_expense.html`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (not applicable here)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Ownership check: after fetching the expense by `id`, verify `expense["user_id"] == session["user_id"]`. If the expense does not exist or belongs to another user, call `abort(404)`
- Import `abort` from `flask` at the top of `app.py`
- On GET: populate the form from the fetched expense row
- On POST: apply the same validation rules as `add_expense` (positive amount, valid category, valid date, description ≤ 200 chars)
- On validation failure: re-render `edit_expense.html` with the submitted (not original) values preserved and an error message
- On success: `UPDATE expenses SET amount=?, category=?, date=?, description=? WHERE id=? AND user_id=?` then redirect to `url_for('profile')`
- If the user is not logged in, redirect to `/login`

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` when logged out redirects to `/login`
- [ ] Visiting `/expenses/<id>/edit` for an expense that belongs to another user returns 404
- [ ] Visiting `/expenses/<id>/edit` for a non-existent id returns 404
- [ ] Visiting `/expenses/<id>/edit` when logged in renders a form with all four fields prefilled with the existing expense data
- [ ] Submitting the form with valid data updates the row in the `expenses` table and redirects to `/profile`
- [ ] The updated values are visible on the profile page after submission
- [ ] Submitting with a missing or zero amount re-renders the form with an error and preserves submitted field values
- [ ] Submitting with an invalid category re-renders the form with an error
- [ ] Submitting with an invalid date re-renders the form with an error
- [ ] Each transaction row on the profile page has a visible "Edit" link that navigates to the correct edit URL
