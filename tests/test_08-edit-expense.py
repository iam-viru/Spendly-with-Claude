"""
tests/test_08-edit-expense.py

Pytest tests for the Edit Expense feature (Step 08).
Spec: .claude/specs/08-edit-expense.md

All tests are based exclusively on the spec's stated behaviour and the
"Definition of done" / "Rules for implementation" sections.
Tests never read implementation code for logic — they define what the
feature *should* do.

Isolation strategy: a temporary file-based SQLite DB (via tmp_path) is
created per test by monkey-patching database.db.DB_PATH, matching the
established convention in this test suite (see test_06 and test_07).
"""

import sqlite3

import pytest
from werkzeug.security import generate_password_hash

from app import app as flask_app
from database.db import init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path):
    """
    Flask app wired to a fresh temporary SQLite file per test.
    get_db() opens connections using the module-level DB_PATH, so
    monkey-patching that path is all that is needed for full isolation.
    """
    db_file = tmp_path / "test_spendly.db"

    import database.db as db_module
    original_path = db_module.DB_PATH
    db_module.DB_PATH = str(db_file)

    flask_app.config.update({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key",
        "WTF_CSRF_ENABLED": False,
    })

    with flask_app.app_context():
        init_db()
        yield flask_app

    db_module.DB_PATH = original_path


@pytest.fixture
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# DB helper utilities
# ---------------------------------------------------------------------------

def _db_path():
    """Return the current monkey-patched DB_PATH."""
    import database.db as db_module
    return db_module.DB_PATH


def _create_user(db_path: str, name: str, email: str, password: str) -> int:
    """Insert a user and return their id."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    with conn:
        conn.execute(
            "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
            (name, email, generate_password_hash(password)),
        )
    user_id = conn.execute(
        "SELECT id FROM users WHERE email = ?", (email,)
    ).fetchone()["id"]
    conn.close()
    return user_id


def _create_expense(
    db_path: str,
    user_id: int,
    amount: float = 20.00,
    category: str = "Food",
    date: str = "2026-05-01",
    description: str = "Test expense",
) -> int:
    """Insert an expense and return its id."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    with conn:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, date, description),
        )
    expense_id = conn.execute(
        "SELECT id FROM expenses WHERE user_id = ? ORDER BY id DESC LIMIT 1",
        (user_id,),
    ).fetchone()["id"]
    conn.close()
    return expense_id


def _get_expense(db_path: str, expense_id: int) -> sqlite3.Row:
    """Fetch a single expense row by id."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM expenses WHERE id = ?", (expense_id,)
    ).fetchone()
    conn.close()
    return row


def _login(client, email: str, password: str):
    """Log in via the login form."""
    return client.post("/login", data={"email": email, "password": password})


def _set_session_user(client, user_id: int):
    """Directly set session['user_id'] without going through the login form."""
    with client.session_transaction() as sess:
        sess["user_id"] = user_id
        sess["user_name"] = "Test User"


# ---------------------------------------------------------------------------
# Convenience fixture: a logged-in client with one owned expense
# ---------------------------------------------------------------------------

@pytest.fixture
def owned_expense(app, client):
    """
    Returns (client, user_id, expense_id) where client is logged in as the
    owner of the expense.
    """
    uid = _create_user(_db_path(), "Owner", "owner@test.com", "ownerpass1")
    exp_id = _create_expense(
        _db_path(),
        uid,
        amount=42.00,
        category="Food",
        date="2026-04-10",
        description="Original description",
    )
    _set_session_user(client, uid)
    return client, uid, exp_id


# ---------------------------------------------------------------------------
# 1. Auth guard — GET
# ---------------------------------------------------------------------------

class TestAuthGuardGet:
    def test_unauthenticated_get_redirects(self, app, client):
        """GET /expenses/<id>/edit when logged out must redirect."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)

        response = client.get(f"/expenses/{exp_id}/edit")
        assert response.status_code == 302, (
            "Unauthenticated GET /expenses/<id>/edit must redirect (302)"
        )

    def test_unauthenticated_get_redirects_to_login(self, app, client):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)

        response = client.get(f"/expenses/{exp_id}/edit")
        assert "/login" in response.headers["Location"], (
            "Unauthenticated GET must redirect to /login"
        )

    def test_unauthenticated_get_does_not_return_200(self, app, client):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)

        response = client.get(f"/expenses/{exp_id}/edit")
        assert response.status_code != 200, (
            "Unauthenticated GET must never return 200"
        )


# ---------------------------------------------------------------------------
# 2. Auth guard — POST
# ---------------------------------------------------------------------------

class TestAuthGuardPost:
    def test_unauthenticated_post_redirects(self, app, client):
        """POST /expenses/<id>/edit when logged out must redirect."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-05-01",
            "description": "updated",
        })
        assert response.status_code == 302, (
            "Unauthenticated POST /expenses/<id>/edit must redirect (302)"
        )

    def test_unauthenticated_post_redirects_to_login(self, app, client):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-05-01",
            "description": "updated",
        })
        assert "/login" in response.headers["Location"], (
            "Unauthenticated POST must redirect to /login"
        )

    def test_unauthenticated_post_does_not_modify_db(self, app, client):
        """A POST from a logged-out user must not modify the expense row."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(
            _db_path(), uid, description="should not change"
        )

        client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "99.00",
            "category": "Bills",
            "date": "2026-01-01",
            "description": "changed by attacker",
        })

        row = _get_expense(_db_path(), exp_id)
        assert row["description"] == "should not change", (
            "Unauthenticated POST must not alter the expense row"
        )


# ---------------------------------------------------------------------------
# 3. Ownership check — another user's expense returns 404
# ---------------------------------------------------------------------------

class TestOwnershipCheck:
    def test_other_users_expense_returns_404(self, app, client):
        """A logged-in user visiting another user's edit URL must receive 404."""
        owner_id = _create_user(_db_path(), "Owner", "owner@t.com", "ownerpass1")
        attacker_id = _create_user(_db_path(), "Attacker", "atk@t.com", "atkpass1")
        exp_id = _create_expense(_db_path(), owner_id, description="private")

        # Log in as attacker
        _set_session_user(client, attacker_id)

        response = client.get(f"/expenses/{exp_id}/edit")
        assert response.status_code == 404, (
            "Accessing another user's expense edit URL must return 404"
        )

    def test_other_users_expense_post_returns_404(self, app, client):
        """A logged-in user POSTing to another user's edit URL must receive 404."""
        owner_id = _create_user(_db_path(), "Owner", "owner@t.com", "ownerpass1")
        attacker_id = _create_user(_db_path(), "Attacker", "atk@t.com", "atkpass1")
        exp_id = _create_expense(_db_path(), owner_id)

        _set_session_user(client, attacker_id)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "1.00",
            "category": "Food",
            "date": "2026-05-01",
            "description": "hijacked",
        })
        assert response.status_code == 404, (
            "POST to another user's expense edit URL must return 404"
        )

    def test_other_users_expense_post_does_not_modify_db(self, app, client):
        """The ownership-guarded POST must leave the original expense untouched."""
        owner_id = _create_user(_db_path(), "Owner", "owner@t.com", "ownerpass1")
        attacker_id = _create_user(_db_path(), "Attacker", "atk@t.com", "atkpass1")
        exp_id = _create_expense(
            _db_path(), owner_id, amount=50.00, description="owner's data"
        )

        _set_session_user(client, attacker_id)
        client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "1.00",
            "category": "Food",
            "date": "2026-05-01",
            "description": "hijacked",
        })

        row = _get_expense(_db_path(), exp_id)
        assert row["description"] == "owner's data", (
            "Ownership check must prevent the expense from being modified"
        )


# ---------------------------------------------------------------------------
# 4. Non-existent expense returns 404
# ---------------------------------------------------------------------------

class TestNonExistentExpense:
    def test_nonexistent_id_get_returns_404(self, app, client):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        _set_session_user(client, uid)

        response = client.get("/expenses/999999/edit")
        assert response.status_code == 404, (
            "GET for a non-existent expense id must return 404"
        )

    def test_nonexistent_id_post_returns_404(self, app, client):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        _set_session_user(client, uid)

        response = client.post("/expenses/999999/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-05-01",
            "description": "ghost",
        })
        assert response.status_code == 404, (
            "POST for a non-existent expense id must return 404"
        )


# ---------------------------------------------------------------------------
# 5. GET happy path — form renders prefilled
# ---------------------------------------------------------------------------

class TestGetEditFormHappyPath:
    def test_get_returns_200(self, owned_expense):
        client, uid, exp_id = owned_expense
        response = client.get(f"/expenses/{exp_id}/edit")
        assert response.status_code == 200, (
            "Authenticated GET for own expense must return 200"
        )

    def test_form_prefills_amount(self, owned_expense):
        client, uid, exp_id = owned_expense
        response = client.get(f"/expenses/{exp_id}/edit")
        html = response.data.decode()
        # The fixture creates amount=42.00; it may be stored as "42.0" or "42.00"
        assert "42" in html, (
            "Edit form must prefill the amount field with the stored value"
        )

    def test_form_prefills_category(self, owned_expense):
        client, uid, exp_id = owned_expense
        response = client.get(f"/expenses/{exp_id}/edit")
        html = response.data.decode()
        assert "Food" in html, (
            "Edit form must prefill the category field with the stored value"
        )

    def test_form_prefills_date(self, owned_expense):
        client, uid, exp_id = owned_expense
        response = client.get(f"/expenses/{exp_id}/edit")
        html = response.data.decode()
        assert "2026-04-10" in html, (
            "Edit form must prefill the date field with the stored value"
        )

    def test_form_prefills_description(self, owned_expense):
        client, uid, exp_id = owned_expense
        response = client.get(f"/expenses/{exp_id}/edit")
        html = response.data.decode()
        assert "Original description" in html, (
            "Edit form must prefill the description field with the stored value"
        )

    def test_form_has_amount_input(self, owned_expense):
        client, uid, exp_id = owned_expense
        response = client.get(f"/expenses/{exp_id}/edit")
        html = response.data.decode()
        assert 'name="amount"' in html, "Edit form must have an amount input"

    def test_form_has_category_field(self, owned_expense):
        client, uid, exp_id = owned_expense
        response = client.get(f"/expenses/{exp_id}/edit")
        html = response.data.decode()
        assert 'name="category"' in html, "Edit form must have a category field"

    def test_form_has_date_input(self, owned_expense):
        client, uid, exp_id = owned_expense
        response = client.get(f"/expenses/{exp_id}/edit")
        html = response.data.decode()
        assert 'name="date"' in html, "Edit form must have a date input"

    def test_form_has_description_field(self, owned_expense):
        client, uid, exp_id = owned_expense
        response = client.get(f"/expenses/{exp_id}/edit")
        html = response.data.decode()
        assert 'name="description"' in html, "Edit form must have a description field"

    def test_form_contains_all_allowed_categories(self, owned_expense):
        """All seven valid categories must appear in the category dropdown."""
        allowed = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
        client, uid, exp_id = owned_expense
        response = client.get(f"/expenses/{exp_id}/edit")
        html = response.data.decode()
        for cat in allowed:
            assert cat in html, f"Category '{cat}' must be present in the edit form"

    def test_page_title_contains_edit_expense(self, owned_expense):
        """The spec states the title must read 'Edit Expense'."""
        client, uid, exp_id = owned_expense
        response = client.get(f"/expenses/{exp_id}/edit")
        html = response.data.decode()
        assert "Edit Expense" in html, (
            "Page must contain 'Edit Expense' as the heading/title"
        )

    def test_submit_button_reads_update_expense(self, owned_expense):
        """The spec states the submit button must read 'Update Expense'."""
        client, uid, exp_id = owned_expense
        response = client.get(f"/expenses/{exp_id}/edit")
        html = response.data.decode()
        assert "Update Expense" in html, (
            "Submit button must read 'Update Expense'"
        )

    def test_form_action_points_to_edit_route(self, owned_expense):
        """The form's action must point to the correct edit URL."""
        client, uid, exp_id = owned_expense
        response = client.get(f"/expenses/{exp_id}/edit")
        html = response.data.decode()
        assert f"/expenses/{exp_id}/edit" in html, (
            "Form action must point to the expense's edit URL"
        )

    def test_page_extends_base_template(self, owned_expense):
        """All templates extend base.html — page must include the full HTML shell."""
        client, uid, exp_id = owned_expense
        response = client.get(f"/expenses/{exp_id}/edit")
        html = response.data.decode()
        assert "<html" in html.lower(), (
            "Page must include the full HTML structure from base.html"
        )


# ---------------------------------------------------------------------------
# 6. POST happy path — valid update
# ---------------------------------------------------------------------------

class TestPostEditExpenseHappyPath:
    def test_valid_post_redirects_to_profile(self, owned_expense):
        client, uid, exp_id = owned_expense
        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "99.99",
            "category": "Transport",
            "date": "2026-06-15",
            "description": "Updated description",
        })
        assert response.status_code == 302, (
            "Valid POST must redirect (302)"
        )
        assert "/profile" in response.headers["Location"], (
            "Redirect after successful POST must go to /profile"
        )

    def test_valid_post_updates_amount_in_db(self, app, owned_expense):
        client, uid, exp_id = owned_expense
        client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "77.50",
            "category": "Food",
            "date": "2026-04-10",
            "description": "Original description",
        })
        row = _get_expense(_db_path(), exp_id)
        assert abs(float(row["amount"]) - 77.50) < 0.001, (
            "Amount in DB must reflect the updated value"
        )

    def test_valid_post_updates_category_in_db(self, app, owned_expense):
        client, uid, exp_id = owned_expense
        client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "42.00",
            "category": "Bills",
            "date": "2026-04-10",
            "description": "Original description",
        })
        row = _get_expense(_db_path(), exp_id)
        assert row["category"] == "Bills", (
            "Category in DB must reflect the updated value"
        )

    def test_valid_post_updates_date_in_db(self, app, owned_expense):
        client, uid, exp_id = owned_expense
        client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "42.00",
            "category": "Food",
            "date": "2026-12-25",
            "description": "Original description",
        })
        row = _get_expense(_db_path(), exp_id)
        assert row["date"] == "2026-12-25", (
            "Date in DB must reflect the updated value"
        )

    def test_valid_post_updates_description_in_db(self, app, owned_expense):
        client, uid, exp_id = owned_expense
        client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "42.00",
            "category": "Food",
            "date": "2026-04-10",
            "description": "Brand new description",
        })
        row = _get_expense(_db_path(), exp_id)
        assert row["description"] == "Brand new description", (
            "Description in DB must reflect the updated value"
        )

    def test_valid_post_does_not_change_user_id(self, app, owned_expense):
        """The user_id on the row must not change after an edit."""
        client, uid, exp_id = owned_expense
        client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": "Other",
            "date": "2026-04-10",
            "description": "anything",
        })
        row = _get_expense(_db_path(), exp_id)
        assert row["user_id"] == uid, (
            "user_id must remain unchanged after a successful edit"
        )

    def test_valid_post_does_not_create_extra_rows(self, app, owned_expense):
        """An UPDATE must not insert a new row; the total expense count must stay the same."""
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
        before_count = conn.execute(
            "SELECT COUNT(*) FROM expenses"
        ).fetchone()[0]
        conn.close()

        client, uid, exp_id = owned_expense
        client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": "Other",
            "date": "2026-04-10",
            "description": "edit",
        })

        conn = sqlite3.connect(_db_path())
        after_count = conn.execute(
            "SELECT COUNT(*) FROM expenses"
        ).fetchone()[0]
        conn.close()
        assert after_count == before_count, (
            "A successful edit must not insert extra rows into the expenses table"
        )

    def test_valid_post_updated_values_visible_on_profile(self, owned_expense):
        """After a successful edit, the updated description must appear on /profile."""
        client, uid, exp_id = owned_expense
        client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "42.00",
            "category": "Food",
            "date": "2026-04-10",
            "description": "Uniquely updated note",
        })
        response = client.get("/profile")
        html = response.data.decode()
        assert "Uniquely updated note" in html, (
            "Updated expense description must be visible on /profile after a successful edit"
        )

    def test_valid_post_empty_description_accepted(self, app, owned_expense):
        """Empty description is optional — submitting blank must succeed."""
        client, uid, exp_id = owned_expense
        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "42.00",
            "category": "Food",
            "date": "2026-04-10",
            "description": "",
        })
        assert response.status_code == 302, (
            "POST with empty description must redirect (302)"
        )

    def test_valid_post_update_is_scoped_to_correct_row(self, app, client):
        """Editing one expense must not alter another expense belonging to the same user."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id_1 = _create_expense(
            _db_path(), uid, amount=10.00, description="first expense"
        )
        exp_id_2 = _create_expense(
            _db_path(), uid, amount=20.00, description="second expense"
        )

        _set_session_user(client, uid)
        client.post(f"/expenses/{exp_id_1}/edit", data={
            "amount": "55.00",
            "category": "Bills",
            "date": "2026-05-01",
            "description": "edited first",
        })

        row2 = _get_expense(_db_path(), exp_id_2)
        assert row2["description"] == "second expense", (
            "Editing expense #1 must not modify expense #2"
        )
        assert abs(float(row2["amount"]) - 20.00) < 0.001, (
            "Editing expense #1 must not change expense #2's amount"
        )


# ---------------------------------------------------------------------------
# 7. POST validation — amount
# ---------------------------------------------------------------------------

class TestAmountValidation:
    @pytest.mark.parametrize("bad_amount", [
        "",         # missing
        "0",        # zero integer
        "0.00",     # zero as float string
        "-1",       # negative
        "-0.01",    # small negative
        "abc",      # non-numeric
        "twelve",   # word
        " ",        # whitespace only
    ])
    def test_invalid_amount_rerenders_form(self, app, client, bad_amount):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": bad_amount,
            "category": "Food",
            "date": "2026-05-01",
            "description": "test",
        })
        assert response.status_code == 200, (
            f"Amount '{bad_amount}' must re-render the form (200), not redirect"
        )

    @pytest.mark.parametrize("bad_amount", ["", "0", "-5.00", "notanumber"])
    def test_invalid_amount_shows_error_message(self, app, client, bad_amount):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": bad_amount,
            "category": "Food",
            "date": "2026-05-01",
            "description": "test",
        })
        html = response.data.decode()
        assert (
            "amount" in html.lower()
            or "positive" in html.lower()
            or "error" in html.lower()
        ), f"Amount '{bad_amount}' must produce a visible error message"

    @pytest.mark.parametrize("bad_amount", ["", "0", "-1.00", "abc"])
    def test_invalid_amount_does_not_update_db(self, app, client, bad_amount):
        uid = _create_user(
            _db_path(), "U", "u@t.com", "password1"
        )
        exp_id = _create_expense(
            _db_path(), uid, amount=30.00, description="unchanged"
        )
        _set_session_user(client, uid)

        client.post(f"/expenses/{exp_id}/edit", data={
            "amount": bad_amount,
            "category": "Food",
            "date": "2026-05-01",
            "description": "changed",
        })

        row = _get_expense(_db_path(), exp_id)
        assert abs(float(row["amount"]) - 30.00) < 0.001, (
            f"Amount '{bad_amount}' must NOT update the DB row"
        )

    def test_valid_zero_point_one_amount_accepted(self, app, client):
        """Smallest positive decimal must be accepted."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "0.01",
            "category": "Food",
            "date": "2026-05-01",
            "description": "",
        })
        assert response.status_code == 302, "Amount 0.01 (smallest positive) must be accepted"

    def test_invalid_amount_preserves_other_submitted_fields(self, app, client):
        """On amount validation failure, other submitted values must be present in the response."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "",
            "category": "Transport",
            "date": "2026-06-20",
            "description": "preserved note",
        })
        html = response.data.decode()
        assert "Transport" in html, (
            "Submitted category must be preserved in the re-rendered form when amount is invalid"
        )
        assert "2026-06-20" in html, (
            "Submitted date must be preserved in the re-rendered form when amount is invalid"
        )
        assert "preserved note" in html, (
            "Submitted description must be preserved in the re-rendered form when amount is invalid"
        )


# ---------------------------------------------------------------------------
# 8. POST validation — category
# ---------------------------------------------------------------------------

class TestCategoryValidation:
    @pytest.mark.parametrize("bad_category", [
        "",                  # empty
        "food",              # wrong case
        "FOOD",              # all caps
        "Groceries",         # not in list
        "None",              # string None
        "Other;DROP TABLE",  # injection-like
        "invalid_cat",       # arbitrary string
    ])
    def test_invalid_category_rerenders_form(self, app, client, bad_category):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": bad_category,
            "date": "2026-05-01",
            "description": "test",
        })
        assert response.status_code == 200, (
            f"Category '{bad_category}' must re-render the form (200)"
        )

    @pytest.mark.parametrize("bad_category", ["", "invalid_cat", "food"])
    def test_invalid_category_shows_error_message(self, app, client, bad_category):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": bad_category,
            "date": "2026-05-01",
            "description": "test",
        })
        html = response.data.decode()
        assert (
            "category" in html.lower()
            or "valid" in html.lower()
            or "error" in html.lower()
        ), f"Category '{bad_category}' must produce a visible error message"

    @pytest.mark.parametrize("bad_category", ["", "Groceries", "food"])
    def test_invalid_category_does_not_update_db(self, app, client, bad_category):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(
            _db_path(), uid, category="Food", description="untouched"
        )
        _set_session_user(client, uid)

        client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": bad_category,
            "date": "2026-05-01",
            "description": "changed",
        })

        row = _get_expense(_db_path(), exp_id)
        assert row["category"] == "Food", (
            f"Category '{bad_category}' must NOT update the DB row"
        )

    def test_all_valid_categories_accepted_on_edit(self, app, client):
        """Every category in the fixed list must be accepted by POST."""
        allowed = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
        for cat in allowed:
            uid = _create_user(
                _db_path(), f"User{cat}", f"{cat.lower()}@t.com", "password1"
            )
            exp_id = _create_expense(_db_path(), uid)
            _set_session_user(client, uid)

            response = client.post(f"/expenses/{exp_id}/edit", data={
                "amount": "10.00",
                "category": cat,
                "date": "2026-05-01",
                "description": "",
            })
            assert response.status_code == 302, (
                f"Category '{cat}' must be accepted by the edit form — expected 302"
            )

    def test_invalid_category_preserves_submitted_amount(self, app, client):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "88.88",
            "category": "NotACategory",
            "date": "2026-05-01",
            "description": "preserved",
        })
        html = response.data.decode()
        assert "88.88" in html, (
            "Submitted amount must be preserved in re-rendered form when category is invalid"
        )


# ---------------------------------------------------------------------------
# 9. POST validation — date
# ---------------------------------------------------------------------------

class TestDateValidation:
    @pytest.mark.parametrize("bad_date", [
        "",               # missing
        "not-a-date",     # garbage string
        "2026/05/01",     # wrong separator
        "01-05-2026",     # day-month-year order
        "20260501",       # no separators
        "2026-13-01",     # invalid month
        "2026-04-31",     # April has 30 days
        "abcd-ef-gh",     # all letters
    ])
    def test_invalid_date_rerenders_form(self, app, client, bad_date):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": bad_date,
            "description": "test",
        })
        assert response.status_code == 200, (
            f"Date '{bad_date}' must re-render the form (200)"
        )

    @pytest.mark.parametrize("bad_date", ["", "not-a-date", "2026/05/01"])
    def test_invalid_date_shows_error_message(self, app, client, bad_date):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": bad_date,
            "description": "test",
        })
        html = response.data.decode()
        assert (
            "date" in html.lower()
            or "valid" in html.lower()
            or "error" in html.lower()
        ), f"Date '{bad_date}' must produce a visible error message"

    @pytest.mark.parametrize("bad_date", ["", "not-a-date", "2026/05/01"])
    def test_invalid_date_does_not_update_db(self, app, client, bad_date):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(
            _db_path(), uid, date="2026-01-01", description="original"
        )
        _set_session_user(client, uid)

        client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": bad_date,
            "description": "changed",
        })

        row = _get_expense(_db_path(), exp_id)
        assert row["date"] == "2026-01-01", (
            f"Date '{bad_date}' must NOT update the DB row"
        )

    def test_past_date_is_accepted(self, app, client):
        """A valid past date must be accepted — no future-only restriction."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2010-01-01",
            "description": "",
        })
        assert response.status_code == 302, "A valid past date must be accepted"

    def test_future_date_is_accepted(self, app, client):
        """A valid future date must be accepted — no past-only restriction."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2099-12-31",
            "description": "",
        })
        assert response.status_code == 302, "A valid future date must be accepted"

    def test_invalid_date_preserves_submitted_amount_and_category(self, app, client):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "55.55",
            "category": "Health",
            "date": "not-a-date",
            "description": "",
        })
        html = response.data.decode()
        assert "55.55" in html, (
            "Submitted amount must be preserved when date is invalid"
        )
        assert "Health" in html, (
            "Submitted category must be preserved when date is invalid"
        )


# ---------------------------------------------------------------------------
# 10. POST validation — description length
# ---------------------------------------------------------------------------

class TestDescriptionValidation:
    def test_description_over_200_chars_rerenders_form(self, app, client):
        """Description exceeding 200 characters must cause form re-render."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        long_desc = "x" * 201

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-05-01",
            "description": long_desc,
        })
        assert response.status_code == 200, (
            "Description > 200 chars must re-render the form (200)"
        )

    def test_description_over_200_chars_shows_error(self, app, client):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-05-01",
            "description": "y" * 201,
        })
        html = response.data.decode()
        assert (
            "description" in html.lower()
            or "200" in html
            or "error" in html.lower()
        ), "Description > 200 chars must produce a visible error message"

    def test_description_over_200_chars_does_not_update_db(self, app, client):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(
            _db_path(), uid, description="short original"
        )
        _set_session_user(client, uid)

        client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-05-01",
            "description": "z" * 201,
        })

        row = _get_expense(_db_path(), exp_id)
        assert row["description"] == "short original", (
            "Description > 200 chars must NOT update the DB row"
        )

    def test_description_exactly_200_chars_is_accepted(self, app, client):
        """200-character description is at the boundary and must be accepted."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-05-01",
            "description": "a" * 200,
        })
        assert response.status_code == 302, (
            "Description of exactly 200 characters must be accepted"
        )

    def test_description_over_200_preserves_submitted_amount(self, app, client):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "33.33",
            "category": "Bills",
            "date": "2026-05-01",
            "description": "b" * 201,
        })
        html = response.data.decode()
        assert "33.33" in html, (
            "Submitted amount must be preserved when description is too long"
        )


# ---------------------------------------------------------------------------
# 11. Profile page — edit links per transaction row
# ---------------------------------------------------------------------------

class TestProfileEditLinks:
    def test_profile_shows_edit_link_for_expense(self, app, client):
        """Each transaction row on /profile must have an edit link."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid, description="Linkable expense")
        _set_session_user(client, uid)

        response = client.get("/profile")
        html = response.data.decode()
        assert f"/expenses/{exp_id}/edit" in html, (
            f"Profile page must contain an edit link pointing to /expenses/{exp_id}/edit"
        )

    def test_profile_edit_link_is_an_anchor_tag(self, app, client):
        """The edit link must be an HTML anchor element."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.get("/profile")
        html = response.data.decode()
        # Expect an <a ... href="...edit..."> element somewhere on the page
        assert f'href="/expenses/{exp_id}/edit"' in html, (
            "Edit link must be an <a> tag with the correct href"
        )

    def test_profile_edit_link_visible_text(self, app, client):
        """The edit link must have visible text (e.g. 'Edit')."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        response = client.get("/profile")
        html = response.data.decode()
        assert "Edit" in html, (
            "The edit link text 'Edit' must appear on the profile page"
        )

    def test_profile_edit_links_for_multiple_expenses(self, app, client):
        """If a user has multiple expenses, each must have its own unique edit link."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id_1 = _create_expense(
            _db_path(), uid, amount=10.00, description="first"
        )
        exp_id_2 = _create_expense(
            _db_path(), uid, amount=20.00, description="second"
        )
        _set_session_user(client, uid)

        response = client.get("/profile")
        html = response.data.decode()
        assert f"/expenses/{exp_id_1}/edit" in html, (
            "Profile must show an edit link for the first expense"
        )
        assert f"/expenses/{exp_id_2}/edit" in html, (
            "Profile must show an edit link for the second expense"
        )

    def test_profile_edit_link_navigates_to_prefilled_form(self, app, client):
        """Following an edit link must return 200 with the expense's data prefilled."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(
            _db_path(), uid, amount=15.00, description="clickable expense"
        )
        _set_session_user(client, uid)

        # Simulate following the edit link
        response = client.get(f"/expenses/{exp_id}/edit")
        assert response.status_code == 200, (
            "Following the edit link must render the prefilled edit form (200)"
        )
        html = response.data.decode()
        assert "clickable expense" in html, (
            "Edit form reached via the profile edit link must prefill the description"
        )

    def test_profile_only_shows_own_edit_links(self, app, client):
        """A user must not see edit links for another user's expenses."""
        uid_a = _create_user(_db_path(), "A", "a@t.com", "passwordA1")
        uid_b = _create_user(_db_path(), "B", "b@t.com", "passwordB1")
        exp_id_a = _create_expense(
            _db_path(), uid_a, description="User A private"
        )

        # Log in as B
        _set_session_user(client, uid_b)

        response = client.get("/profile")
        html = response.data.decode()
        assert f"/expenses/{exp_id_a}/edit" not in html, (
            "User B's profile must not contain an edit link for User A's expense"
        )


# ---------------------------------------------------------------------------
# HTTP semantics — consolidated checks
# ---------------------------------------------------------------------------

class TestHttpSemantics:
    def test_get_own_expense_returns_200(self, owned_expense):
        client, uid, exp_id = owned_expense
        assert client.get(f"/expenses/{exp_id}/edit").status_code == 200

    def test_successful_post_returns_302(self, owned_expense):
        client, uid, exp_id = owned_expense
        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-05-01",
            "description": "",
        })
        assert response.status_code == 302

    def test_validation_failure_returns_200_not_302(self, owned_expense):
        client, uid, exp_id = owned_expense
        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "",           # invalid
            "category": "Food",
            "date": "2026-05-01",
            "description": "",
        })
        assert response.status_code == 200, (
            "Validation failure must re-render the form (200), not redirect"
        )

    def test_successful_post_location_header_contains_profile(self, owned_expense):
        client, uid, exp_id = owned_expense
        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-05-01",
            "description": "",
        })
        assert "/profile" in response.headers["Location"], (
            "302 Location header must point to /profile"
        )

    def test_unauthenticated_get_is_302_not_200(self, app, client):
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        response = client.get(f"/expenses/{exp_id}/edit")
        assert response.status_code == 302

    def test_wrong_owner_get_is_404_not_200(self, app, client):
        owner_id = _create_user(_db_path(), "Owner", "owner@t.com", "ownerpass1")
        other_id = _create_user(_db_path(), "Other", "other@t.com", "otherpass1")
        exp_id = _create_expense(_db_path(), owner_id)
        _set_session_user(client, other_id)
        response = client.get(f"/expenses/{exp_id}/edit")
        assert response.status_code == 404


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_sql_injection_in_description_stored_safely(self, app, client):
        """Parameterised queries must store injection attempts as literal text."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        malicious = "'; UPDATE expenses SET amount=9999 WHERE '1'='1"
        response = client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "5.00",
            "category": "Other",
            "date": "2026-05-01",
            "description": malicious,
        })
        assert response.status_code == 302, (
            "SQL injection in description must not prevent a successful update"
        )

        row = _get_expense(_db_path(), exp_id)
        assert row["description"] == malicious, (
            "Malicious description must be stored as literal text, not executed"
        )
        assert abs(float(row["amount"]) - 5.00) < 0.001, (
            "amount must be the submitted value, not altered by injected SQL"
        )

    def test_expenses_table_survives_injection_in_description(self, app, client):
        """The expenses table must still exist after an injection attempt in description."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "1.00",
            "category": "Other",
            "date": "2026-05-01",
            "description": "'; DROP TABLE expenses; --",
        })

        conn = sqlite3.connect(_db_path())
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='expenses'"
        ).fetchall()
        conn.close()
        assert len(tables) == 1, "expenses table must still exist after injection attempt"

    def test_very_long_valid_description_at_boundary(self, app, client):
        """200-char description (boundary value) must be stored in full."""
        uid = _create_user(_db_path(), "U", "u@t.com", "password1")
        exp_id = _create_expense(_db_path(), uid)
        _set_session_user(client, uid)

        boundary_desc = "a" * 200
        client.post(f"/expenses/{exp_id}/edit", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-05-01",
            "description": boundary_desc,
        })

        row = _get_expense(_db_path(), exp_id)
        assert row["description"] == boundary_desc, (
            "A 200-character description must be stored verbatim"
        )

    def test_edit_does_not_affect_different_users_row_with_same_expense_id(
        self, app, client
    ):
        """
        Even if two users exist with sequentially assigned expense IDs, editing
        one user's expense must only touch that user's row.
        """
        uid_a = _create_user(_db_path(), "A", "a@t.com", "passwordA1")
        uid_b = _create_user(_db_path(), "B", "b@t.com", "passwordB1")

        # Create expense for A first, then for B — IDs are assigned sequentially
        exp_id_a = _create_expense(
            _db_path(), uid_a, amount=100.00, description="A expense"
        )
        _create_expense(
            _db_path(), uid_b, amount=200.00, description="B expense"
        )

        # Log in as A and edit A's expense
        _set_session_user(client, uid_a)
        client.post(f"/expenses/{exp_id_a}/edit", data={
            "amount": "111.00",
            "category": "Bills",
            "date": "2026-05-01",
            "description": "A updated",
        })

        # Verify B's expense is untouched
        conn = sqlite3.connect(_db_path())
        conn.row_factory = sqlite3.Row
        row_b = conn.execute(
            "SELECT * FROM expenses WHERE user_id = ?", (uid_b,)
        ).fetchone()
        conn.close()

        assert abs(float(row_b["amount"]) - 200.00) < 0.001, (
            "Editing User A's expense must not alter User B's expense amount"
        )
        assert row_b["description"] == "B expense", (
            "Editing User A's expense must not alter User B's expense description"
        )
