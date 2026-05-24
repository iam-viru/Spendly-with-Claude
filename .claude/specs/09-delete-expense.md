# Spec: Delete Expense

## Overview
Allows a logged-in user to permanently delete one of their own expenses. This completes the full CRUD lifecycle for expenses (Create in step 07, Read in step 05, Update in step 08, Delete here). The placeholder route at `GET /expenses/<id>/delete` is replaced with a secure `POST`-only handler so the delete cannot be triggered by a prefetch or link crawl.

## Depends on
- Step 01 — Database setup (expenses table)
- Step 03 — Login and session (auth guard)
- Step 05 — Profile page backend (expense list with IDs)
- Step 08 — Edit expense (ownership check pattern)

## Routes
- `POST /expenses/<int:id>/delete` — deletes the expense owned by the current user — logged-in only

The existing `GET /expenses/<int:id>/delete` placeholder must be removed and replaced with this POST-only route.

## Database changes
No database changes. The existing `expenses` table is sufficient — a parameterised `DELETE` against `id` and `user_id` is all that's needed.

## Templates
- **Modify:** `templates/profile.html` — add a small delete form (POST) next to each expense row in the recent expenses list. The form should contain a hidden `_method` field is NOT needed — use a real POST form with a submit button styled as a danger link/button.

## Files to change
- `app.py` — replace the placeholder `delete_expense` route with a real POST handler
- `templates/profile.html` — add a delete button/form per expense row

## Files to create
No new files.

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — `DELETE FROM expenses WHERE id = ? AND user_id = ?`
- Always verify ownership in the same query (using `AND user_id = ?`) — never fetch then delete separately
- If the expense does not exist or belongs to another user, return `abort(404)`
- Route must be `POST` only — decorate with `methods=["POST"]` and remove the old GET placeholder
- Redirect to `url_for("profile")` on success
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- Delete button must be inside a `<form method="post">` — no JavaScript fetch or XHR required

## Definition of done
- [ ] Visiting `GET /expenses/<id>/delete` returns 405 Method Not Allowed (route is POST-only)
- [ ] Submitting the delete form for an expense owned by the logged-in user removes it and redirects to `/profile`
- [ ] The deleted expense no longer appears in the profile expense list after deletion
- [ ] Attempting to delete an expense belonging to a different user returns 404
- [ ] Attempting to delete a non-existent expense ID returns 404
- [ ] The delete button is visible on each expense row in `profile.html`
- [ ] A logged-out user POSTing to `/expenses/<id>/delete` is redirected to `/login`
