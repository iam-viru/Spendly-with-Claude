"""
tests/test_07-add-expense.py

Pytest tests for the Add Expense feature.
Spec: .claude/specs/07-add-expense.md

All tests are based exclusively on the spec's stated behaviour.
The temporary file-based SQLite database is rebuilt for every test so tests are
fully independent. The DB_PATH monkey-patch pattern matches the established
convention in this test suite (see test_06-date-filter-for-profile-page.py).
"""

import sqlite3
from datetime import date

import pytest

from app import app as flask_app
from database.db import init_db


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path):
    """
    Flask app wired to a temporary SQLite file so each test gets a clean DB.
    get_db() opens a new connection each call using the module-level DB_PATH,
    so we monkey-patch that path to point at a temp file.
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


@pytest.fixture
def auth_client(client):
    """Test client that has already registered and is logged in."""
    client.post("/register", data={
        "name": "Expense Tester",
        "email": "expense@test.com",
        "password": "securepass1",
    })
    # register() sets the session on success — user is now logged in
    return client


def _get_user_id(db_path: str, email: str) -> int:
    """Return the id of the user with the given email from the test DB."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return row["id"]


def _get_expenses_for_user(db_path: str, user_id: int) -> list:
    """Return all expense rows (as sqlite3.Row objects) for user_id."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM expenses WHERE user_id = ? ORDER BY id ASC",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_unauthenticated_get_redirects_to_login(self, client):
        response = client.get("/expenses/add")
        assert response.status_code == 302, (
            "Unauthenticated GET /expenses/add must redirect"
        )
        assert "/login" in response.headers["Location"], (
            "Redirect target must be /login"
        )

    def test_unauthenticated_post_redirects_to_login(self, client):
        response = client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-05-01",
            "description": "lunch",
        })
        assert response.status_code == 302, (
            "Unauthenticated POST /expenses/add must redirect"
        )
        assert "/login" in response.headers["Location"], (
            "Redirect target must be /login"
        )

    def test_unauthenticated_get_does_not_return_200(self, client):
        response = client.get("/expenses/add")
        assert response.status_code != 200, (
            "Unauthenticated /expenses/add must not return 200"
        )


# ---------------------------------------------------------------------------
# GET /expenses/add — form rendering
# ---------------------------------------------------------------------------

class TestGetAddExpenseForm:
    def test_authenticated_get_returns_200(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert response.status_code == 200, (
            "Authenticated GET /expenses/add must return 200"
        )

    def test_form_contains_amount_field(self, auth_client):
        response = auth_client.get("/expenses/add")
        html = response.data.decode()
        assert 'name="amount"' in html, "Form must contain an amount input field"

    def test_form_contains_category_field(self, auth_client):
        response = auth_client.get("/expenses/add")
        html = response.data.decode()
        assert 'name="category"' in html, "Form must contain a category field"

    def test_form_contains_date_field(self, auth_client):
        response = auth_client.get("/expenses/add")
        html = response.data.decode()
        assert 'name="date"' in html, "Form must contain a date input field"

    def test_form_contains_description_field(self, auth_client):
        response = auth_client.get("/expenses/add")
        html = response.data.decode()
        assert 'name="description"' in html, "Form must contain a description field"

    def test_date_field_defaults_to_today(self, auth_client):
        today_iso = date.today().isoformat()
        response = auth_client.get("/expenses/add")
        html = response.data.decode()
        assert today_iso in html, (
            f"Date field must default to today's date ({today_iso})"
        )

    def test_form_contains_all_allowed_categories(self, auth_client):
        allowed = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
        response = auth_client.get("/expenses/add")
        html = response.data.decode()
        for cat in allowed:
            assert cat in html, f"Category dropdown must include '{cat}'"

    def test_form_has_submit_button(self, auth_client):
        response = auth_client.get("/expenses/add")
        html = response.data.decode()
        assert "submit" in html.lower(), "Form must contain a submit button"

    def test_page_extends_base_template(self, auth_client):
        """All templates extend base.html which injects the navbar."""
        response = auth_client.get("/expenses/add")
        html = response.data.decode()
        # base.html renders the <html> root; check for a landmark that base provides
        assert "<html" in html.lower(), (
            "Rendered page must include the full HTML structure from base.html"
        )

    def test_form_submits_to_add_expense_route(self, auth_client):
        response = auth_client.get("/expenses/add")
        html = response.data.decode()
        assert "/expenses/add" in html, (
            "Form action must point to /expenses/add"
        )


# ---------------------------------------------------------------------------
# POST /expenses/add — happy path
# ---------------------------------------------------------------------------

class TestPostAddExpenseHappyPath:
    def test_valid_post_redirects_to_profile(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "25.50",
            "category": "Food",
            "date": "2026-05-01",
            "description": "Lunch at cafe",
        })
        assert response.status_code == 302, (
            "Valid POST must redirect (302)"
        )
        assert "/profile" in response.headers["Location"], (
            "Redirect after successful POST must go to /profile"
        )

    def test_valid_post_inserts_row_in_db(self, app, auth_client):
        import database.db as db_module

        auth_client.post("/expenses/add", data={
            "amount": "25.50",
            "category": "Food",
            "date": "2026-05-01",
            "description": "Lunch at cafe",
        })

        user_id = _get_user_id(db_module.DB_PATH, "expense@test.com")
        expenses = _get_expenses_for_user(db_module.DB_PATH, user_id)

        assert len(expenses) == 1, "Exactly one expense row must be inserted after a valid POST"

    def test_valid_post_stores_correct_amount(self, app, auth_client):
        import database.db as db_module

        auth_client.post("/expenses/add", data={
            "amount": "25.50",
            "category": "Food",
            "date": "2026-05-01",
            "description": "Lunch",
        })

        user_id = _get_user_id(db_module.DB_PATH, "expense@test.com")
        expenses = _get_expenses_for_user(db_module.DB_PATH, user_id)

        assert abs(expenses[0]["amount"] - 25.50) < 0.001, (
            "Stored amount must match submitted value (25.50)"
        )

    def test_valid_post_stores_correct_category(self, app, auth_client):
        import database.db as db_module

        auth_client.post("/expenses/add", data={
            "amount": "12.00",
            "category": "Transport",
            "date": "2026-05-01",
            "description": "",
        })

        user_id = _get_user_id(db_module.DB_PATH, "expense@test.com")
        expenses = _get_expenses_for_user(db_module.DB_PATH, user_id)

        assert expenses[0]["category"] == "Transport", (
            "Stored category must match submitted value"
        )

    def test_valid_post_stores_correct_date(self, app, auth_client):
        import database.db as db_module

        auth_client.post("/expenses/add", data={
            "amount": "8.00",
            "category": "Other",
            "date": "2026-03-15",
            "description": "",
        })

        user_id = _get_user_id(db_module.DB_PATH, "expense@test.com")
        expenses = _get_expenses_for_user(db_module.DB_PATH, user_id)

        assert expenses[0]["date"] == "2026-03-15", (
            "Stored date must match submitted value"
        )

    def test_valid_post_stores_correct_description(self, app, auth_client):
        import database.db as db_module

        auth_client.post("/expenses/add", data={
            "amount": "50.00",
            "category": "Bills",
            "date": "2026-05-01",
            "description": "Monthly internet bill",
        })

        user_id = _get_user_id(db_module.DB_PATH, "expense@test.com")
        expenses = _get_expenses_for_user(db_module.DB_PATH, user_id)

        assert expenses[0]["description"] == "Monthly internet bill", (
            "Stored description must match submitted value"
        )

    def test_valid_post_stores_correct_user_id(self, app, auth_client):
        import database.db as db_module

        auth_client.post("/expenses/add", data={
            "amount": "15.00",
            "category": "Health",
            "date": "2026-05-01",
            "description": "",
        })

        user_id = _get_user_id(db_module.DB_PATH, "expense@test.com")
        expenses = _get_expenses_for_user(db_module.DB_PATH, user_id)

        assert expenses[0]["user_id"] == user_id, (
            "Stored user_id must match the logged-in user's id"
        )

    def test_valid_post_without_description_succeeds(self, app, auth_client):
        """description is optional — omitting it must still insert a row."""
        import database.db as db_module

        response = auth_client.post("/expenses/add", data={
            "amount": "9.99",
            "category": "Shopping",
            "date": "2026-05-01",
            # description intentionally absent
        })

        assert response.status_code == 302, (
            "POST without description must still redirect (302)"
        )

        user_id = _get_user_id(db_module.DB_PATH, "expense@test.com")
        expenses = _get_expenses_for_user(db_module.DB_PATH, user_id)

        assert len(expenses) == 1, "A row must be inserted even when description is omitted"

    def test_valid_post_with_empty_description_succeeds(self, app, auth_client):
        """Empty string description is also optional and must be accepted."""
        import database.db as db_module

        response = auth_client.post("/expenses/add", data={
            "amount": "5.00",
            "category": "Entertainment",
            "date": "2026-05-01",
            "description": "",
        })

        assert response.status_code == 302, (
            "POST with empty description must redirect (302)"
        )

        user_id = _get_user_id(db_module.DB_PATH, "expense@test.com")
        expenses = _get_expenses_for_user(db_module.DB_PATH, user_id)
        assert len(expenses) == 1, "A row must be inserted with empty description"

    def test_all_allowed_categories_are_accepted(self, app, auth_client):
        """Every category in the fixed list must be accepted by POST."""
        import database.db as db_module

        allowed = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]
        for cat in allowed:
            response = auth_client.post("/expenses/add", data={
                "amount": "1.00",
                "category": cat,
                "date": "2026-05-01",
                "description": "",
            })
            assert response.status_code == 302, (
                f"Category '{cat}' must be accepted — expected redirect, got {response.status_code}"
            )

        user_id = _get_user_id(db_module.DB_PATH, "expense@test.com")
        expenses = _get_expenses_for_user(db_module.DB_PATH, user_id)
        assert len(expenses) == len(allowed), (
            "One expense row must be inserted per accepted category"
        )

    def test_expense_visible_on_profile_after_submission(self, auth_client):
        """After a successful POST, the new expense must appear on /profile."""
        auth_client.post("/expenses/add", data={
            "amount": "42.00",
            "category": "Food",
            "date": "2026-05-01",
            "description": "Dinner with friends",
        })

        response = auth_client.get("/profile")
        html = response.data.decode()
        assert "Dinner with friends" in html, (
            "Newly added expense description must appear on the profile page"
        )


# ---------------------------------------------------------------------------
# POST /expenses/add — amount validation
# ---------------------------------------------------------------------------

class TestAmountValidation:
    @pytest.mark.parametrize("bad_amount", [
        "",          # missing
        "0",         # zero
        "0.00",      # zero as float string
        "-1",        # negative integer
        "-0.01",     # negative float
        "abc",       # non-numeric
        "twelve",    # word
        " ",         # whitespace only
        "--10",      # double negative
    ])
    def test_invalid_amount_rerenders_form(self, auth_client, bad_amount):
        response = auth_client.post("/expenses/add", data={
            "amount": bad_amount,
            "category": "Food",
            "date": "2026-05-01",
            "description": "test",
        })
        assert response.status_code == 200, (
            f"Amount '{bad_amount}' must re-render the form (200), not redirect"
        )

    @pytest.mark.parametrize("bad_amount", [
        "",
        "0",
        "-5.00",
        "notanumber",
    ])
    def test_invalid_amount_shows_error_message(self, auth_client, bad_amount):
        response = auth_client.post("/expenses/add", data={
            "amount": bad_amount,
            "category": "Food",
            "date": "2026-05-01",
            "description": "test",
        })
        html = response.data.decode()
        assert "amount" in html.lower() or "positive" in html.lower() or "error" in html.lower(), (
            f"Amount '{bad_amount}' must produce a visible error message"
        )

    @pytest.mark.parametrize("bad_amount", [
        "",
        "0",
        "-1.00",
        "abc",
    ])
    def test_invalid_amount_does_not_insert_db_row(self, app, auth_client, bad_amount):
        import database.db as db_module

        auth_client.post("/expenses/add", data={
            "amount": bad_amount,
            "category": "Food",
            "date": "2026-05-01",
            "description": "test",
        })

        user_id = _get_user_id(db_module.DB_PATH, "expense@test.com")
        expenses = _get_expenses_for_user(db_module.DB_PATH, user_id)
        assert len(expenses) == 0, (
            f"Amount '{bad_amount}' must NOT insert a DB row"
        )

    def test_positive_decimal_amount_is_accepted(self, auth_client):
        """A positive decimal such as 0.01 must be accepted."""
        response = auth_client.post("/expenses/add", data={
            "amount": "0.01",
            "category": "Food",
            "date": "2026-05-01",
            "description": "",
        })
        assert response.status_code == 302, "Amount 0.01 must be accepted (positive)"

    def test_large_amount_is_accepted(self, auth_client):
        """No upper bound is specified; a large value must be accepted."""
        response = auth_client.post("/expenses/add", data={
            "amount": "999999.99",
            "category": "Bills",
            "date": "2026-05-01",
            "description": "",
        })
        assert response.status_code == 302, "Large amount must be accepted"


# ---------------------------------------------------------------------------
# POST /expenses/add — category validation
# ---------------------------------------------------------------------------

class TestCategoryValidation:
    @pytest.mark.parametrize("bad_category", [
        "",                 # missing / empty
        "food",             # wrong case
        "FOOD",             # all caps
        "Groceries",        # not in list
        "None",             # string None
        "Other;DROP TABLE", # injection-like
        "invalid_category", # random string
    ])
    def test_invalid_category_rerenders_form(self, auth_client, bad_category):
        response = auth_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": bad_category,
            "date": "2026-05-01",
            "description": "test",
        })
        assert response.status_code == 200, (
            f"Category '{bad_category}' must re-render the form (200)"
        )

    @pytest.mark.parametrize("bad_category", [
        "",
        "invalid_category",
        "food",
    ])
    def test_invalid_category_shows_error_message(self, auth_client, bad_category):
        response = auth_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": bad_category,
            "date": "2026-05-01",
            "description": "test",
        })
        html = response.data.decode()
        assert "category" in html.lower() or "valid" in html.lower() or "error" in html.lower(), (
            f"Category '{bad_category}' must produce a visible error message"
        )

    @pytest.mark.parametrize("bad_category", [
        "",
        "Groceries",
        "food",
    ])
    def test_invalid_category_does_not_insert_db_row(self, app, auth_client, bad_category):
        import database.db as db_module

        auth_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": bad_category,
            "date": "2026-05-01",
            "description": "test",
        })

        user_id = _get_user_id(db_module.DB_PATH, "expense@test.com")
        expenses = _get_expenses_for_user(db_module.DB_PATH, user_id)
        assert len(expenses) == 0, (
            f"Category '{bad_category}' must NOT insert a DB row"
        )


# ---------------------------------------------------------------------------
# POST /expenses/add — date validation
# ---------------------------------------------------------------------------

class TestDateValidation:
    @pytest.mark.parametrize("bad_date", [
        "",                     # missing
        "not-a-date",           # garbage string
        "2026/05/01",           # wrong separator
        "01-05-2026",           # day-month-year order
        "20260501",             # no separators
        "2026-13-01",           # invalid month
        "2026-04-31",           # April has 30 days
        "abcd-ef-gh",           # all letters
    ])
    def test_invalid_date_rerenders_form(self, auth_client, bad_date):
        response = auth_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Food",
            "date": bad_date,
            "description": "test",
        })
        assert response.status_code == 200, (
            f"Date '{bad_date}' must re-render the form (200)"
        )

    @pytest.mark.parametrize("bad_date", [
        "",
        "not-a-date",
        "2026/05/01",
    ])
    def test_invalid_date_shows_error_message(self, auth_client, bad_date):
        response = auth_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Food",
            "date": bad_date,
            "description": "test",
        })
        html = response.data.decode()
        assert "date" in html.lower() or "valid" in html.lower() or "error" in html.lower(), (
            f"Date '{bad_date}' must produce a visible error message"
        )

    @pytest.mark.parametrize("bad_date", [
        "",
        "not-a-date",
        "2026/05/01",
    ])
    def test_invalid_date_does_not_insert_db_row(self, app, auth_client, bad_date):
        import database.db as db_module

        auth_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Food",
            "date": bad_date,
            "description": "test",
        })

        user_id = _get_user_id(db_module.DB_PATH, "expense@test.com")
        expenses = _get_expenses_for_user(db_module.DB_PATH, user_id)
        assert len(expenses) == 0, (
            f"Date '{bad_date}' must NOT insert a DB row"
        )

    def test_past_date_is_accepted(self, auth_client):
        """A valid past date must be accepted — the spec puts no future-only restriction."""
        response = auth_client.post("/expenses/add", data={
            "amount": "20.00",
            "category": "Food",
            "date": "2020-01-01",
            "description": "",
        })
        assert response.status_code == 302, "A valid past date must be accepted"

    def test_future_date_is_accepted(self, auth_client):
        """A valid future date must be accepted — the spec puts no past-only restriction."""
        response = auth_client.post("/expenses/add", data={
            "amount": "20.00",
            "category": "Food",
            "date": "2099-12-31",
            "description": "",
        })
        assert response.status_code == 302, "A valid future date must be accepted"


# ---------------------------------------------------------------------------
# Field preservation on validation failure
# ---------------------------------------------------------------------------

class TestFieldPreservation:
    def test_amount_preserved_on_invalid_category(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "77.77",
            "category": "NotACategory",
            "date": "2026-05-01",
            "description": "preserved description",
        })
        html = response.data.decode()
        assert "77.77" in html, (
            "Submitted amount must be preserved in the re-rendered form when category is invalid"
        )

    def test_description_preserved_on_invalid_category(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "NotACategory",
            "date": "2026-05-01",
            "description": "preserved description",
        })
        html = response.data.decode()
        assert "preserved description" in html, (
            "Submitted description must be preserved in the re-rendered form when category is invalid"
        )

    def test_date_preserved_on_invalid_category(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "NotACategory",
            "date": "2026-05-01",
            "description": "",
        })
        html = response.data.decode()
        assert "2026-05-01" in html, (
            "Submitted date must be preserved in the re-rendered form when category is invalid"
        )

    def test_category_preserved_on_invalid_amount(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "-5",
            "category": "Transport",
            "date": "2026-05-01",
            "description": "",
        })
        html = response.data.decode()
        assert "Transport" in html, (
            "Submitted category must be preserved in the re-rendered form when amount is invalid"
        )

    def test_date_preserved_on_invalid_amount(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "abc",
            "category": "Food",
            "date": "2026-05-01",
            "description": "",
        })
        html = response.data.decode()
        assert "2026-05-01" in html, (
            "Submitted date must be preserved in the re-rendered form when amount is invalid"
        )

    def test_description_preserved_on_invalid_amount(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "",
            "category": "Food",
            "date": "2026-05-01",
            "description": "my preserved note",
        })
        html = response.data.decode()
        assert "my preserved note" in html, (
            "Submitted description must be preserved when amount is invalid"
        )

    def test_amount_preserved_on_invalid_date(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "33.33",
            "category": "Bills",
            "date": "not-a-date",
            "description": "",
        })
        html = response.data.decode()
        assert "33.33" in html, (
            "Submitted amount must be preserved in the re-rendered form when date is invalid"
        )

    def test_category_preserved_on_invalid_date(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Health",
            "date": "not-a-date",
            "description": "",
        })
        html = response.data.decode()
        assert "Health" in html, (
            "Submitted category must be preserved in the re-rendered form when date is invalid"
        )


# ---------------------------------------------------------------------------
# Navbar "Add Expense" link
# ---------------------------------------------------------------------------

class TestNavbarAddExpenseLink:
    def test_navbar_shows_add_expense_link_for_logged_in_user(self, auth_client):
        """The base template must render an 'Add Expense' link for authenticated users."""
        response = auth_client.get("/profile")
        html = response.data.decode()
        assert "/expenses/add" in html, (
            "Navbar must contain a link to /expenses/add for logged-in users"
        )

    def test_add_expense_link_text_on_navbar(self, auth_client):
        response = auth_client.get("/profile")
        html = response.data.decode()
        assert "Add Expense" in html, (
            "Navbar link must have 'Add Expense' as visible text"
        )


# ---------------------------------------------------------------------------
# HTTP semantics
# ---------------------------------------------------------------------------

class TestHttpSemantics:
    def test_get_returns_200(self, auth_client):
        response = auth_client.get("/expenses/add")
        assert response.status_code == 200

    def test_successful_post_returns_302(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-05-01",
            "description": "",
        })
        assert response.status_code == 302

    def test_validation_failure_returns_200_not_302(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "",
            "category": "Food",
            "date": "2026-05-01",
            "description": "",
        })
        assert response.status_code == 200, (
            "Validation failure must re-render the form (200), not redirect"
        )

    def test_successful_post_redirects_to_profile_url(self, auth_client):
        response = auth_client.post("/expenses/add", data={
            "amount": "10.00",
            "category": "Food",
            "date": "2026-05-01",
            "description": "",
        })
        assert "/profile" in response.headers["Location"], (
            "Successful POST must redirect to /profile"
        )


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_sql_injection_in_description_is_safe(self, app, auth_client):
        """Parameterised queries must safely store injection attempts as literal text."""
        import database.db as db_module

        malicious = "'; DROP TABLE expenses; --"
        response = auth_client.post("/expenses/add", data={
            "amount": "1.00",
            "category": "Other",
            "date": "2026-05-01",
            "description": malicious,
        })
        assert response.status_code == 302, (
            "SQL injection in description must not prevent a successful insert"
        )

        user_id = _get_user_id(db_module.DB_PATH, "expense@test.com")
        expenses = _get_expenses_for_user(db_module.DB_PATH, user_id)
        assert len(expenses) == 1, "Expense row must be inserted despite injection attempt in description"
        assert expenses[0]["description"] == malicious, (
            "Malicious description must be stored as literal text (not executed)"
        )

    def test_expenses_table_still_exists_after_injection_attempt(self, app, auth_client):
        """The expenses table must survive an injection attempt in any field."""
        import database.db as db_module

        auth_client.post("/expenses/add", data={
            "amount": "1.00",
            "category": "Other",
            "date": "2026-05-01",
            "description": "'; DROP TABLE expenses; --",
        })

        conn = sqlite3.connect(db_module.DB_PATH)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='expenses'"
        ).fetchall()
        conn.close()
        assert len(tables) == 1, "expenses table must still exist after an injection attempt"

    def test_multiple_expenses_can_be_added_sequentially(self, app, auth_client):
        """Adding two expenses in sequence must result in two rows in the DB."""
        import database.db as db_module

        for i in range(2):
            auth_client.post("/expenses/add", data={
                "amount": f"{10 + i}.00",
                "category": "Food",
                "date": "2026-05-01",
                "description": f"Expense {i}",
            })

        user_id = _get_user_id(db_module.DB_PATH, "expense@test.com")
        expenses = _get_expenses_for_user(db_module.DB_PATH, user_id)
        assert len(expenses) == 2, "Two sequential POSTs must insert two rows"

    def test_data_isolation_between_users(self, app, client):
        """User B must not see User A's expenses after User A adds one."""
        import database.db as db_module

        # Register and log in as User A
        client.post("/register", data={
            "name": "User A",
            "email": "usera@isolation.com",
            "password": "passwordA1",
        })
        client.post("/expenses/add", data={
            "amount": "100.00",
            "category": "Bills",
            "date": "2026-05-01",
            "description": "User A private expense",
        })

        # Register as User B (overwrites session — User B is now logged in)
        client.post("/register", data={
            "name": "User B",
            "email": "userb@isolation.com",
            "password": "passwordB1",
        })

        response = client.get("/profile")
        html = response.data.decode()
        assert "User A private expense" not in html, (
            "User B must not see User A's expense on the profile page"
        )

    def test_amount_with_many_decimal_places_accepted(self, app, auth_client):
        """float() accepts strings with many decimal places; must be stored correctly."""
        import database.db as db_module

        response = auth_client.post("/expenses/add", data={
            "amount": "10.12345",
            "category": "Food",
            "date": "2026-05-01",
            "description": "",
        })
        assert response.status_code == 302, "Amount with many decimals must be accepted"

        user_id = _get_user_id(db_module.DB_PATH, "expense@test.com")
        expenses = _get_expenses_for_user(db_module.DB_PATH, user_id)
        assert len(expenses) == 1, "Row must be inserted for amount with many decimals"
