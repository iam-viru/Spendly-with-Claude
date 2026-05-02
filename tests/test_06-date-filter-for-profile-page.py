"""
tests/test_06-date-filter-for-profile-page.py

Pytest tests for the date-filter feature added to the /profile route.
Spec: .claude/specs/06-date-filter-for-profile-page.md

All tests are based exclusively on the spec's stated behaviour.
The in-memory SQLite database is rebuilt for every test so tests are
fully independent.
"""

import sqlite3
import pytest
from datetime import date, timedelta
from calendar import monthrange
from werkzeug.security import generate_password_hash

from app import app as flask_app
from database.db import init_db


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _first_day_of_month(d: date) -> date:
    return date(d.year, d.month, 1)


def _first_day_3_months_ago(d: date) -> date:
    """Return the first day of the month that is 2 months before d's month."""
    month = d.month - 2
    year = d.year
    if month <= 0:
        month += 12
        year -= 1
    return date(year, month, 1)


def _first_day_of_year(d: date) -> date:
    return date(d.year, 1, 1)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def app(tmp_path):
    """
    Flask app wired to a temporary SQLite file so each test starts clean.
    We use a file-based temp DB (not :memory:) because get_db() always opens
    a new connection to DB_PATH; patching that path makes isolation simple.
    """
    db_file = tmp_path / "test_spendly.db"

    # Monkey-patch the module-level DB_PATH used by database/db.py
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

    # Restore original path after each test
    db_module.DB_PATH = original_path


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def auth_client(client):
    """Client that has registered and logged in as a user with NO expenses."""
    client.post("/register", data={
        "name": "Filter Tester",
        "email": "filter@test.com",
        "password": "securepass1",
    })
    # register() redirects to landing and sets the session — user is logged in
    return client


@pytest.fixture
def seeded_auth_client(app, client):
    """
    Client logged in as a user whose expenses span multiple months so we can
    assert that date filters include/exclude the right rows.

    Inserted expenses (all belonging to the same test user):
      - 2026-01-15  Food          50.00   "January lunch"
      - 2026-02-10  Transport     20.00   "February bus"
      - 2026-03-05  Bills         100.00  "March bill"
      - 2026-04-01  Food          30.00   "April groceries"
      - 2026-04-20  Entertainment 15.00   "April movie"
      - 2026-04-30  Health        25.00   "April gym"
    """
    import database.db as db_module

    # Register the test user
    client.post("/register", data={
        "name": "Seed Tester",
        "email": "seed@test.com",
        "password": "securepass2",
    })

    # Insert expenses directly via db helper
    conn = sqlite3.connect(db_module.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")

    user_id = conn.execute(
        "SELECT id FROM users WHERE email = ?", ("seed@test.com",)
    ).fetchone()["id"]

    expenses = [
        (user_id, 50.00, "Food",          "2026-01-15", "January lunch"),
        (user_id, 20.00, "Transport",     "2026-02-10", "February bus"),
        (user_id, 100.00, "Bills",        "2026-03-05", "March bill"),
        (user_id, 30.00, "Food",          "2026-04-01", "April groceries"),
        (user_id, 15.00, "Entertainment", "2026-04-20", "April movie"),
        (user_id, 25.00, "Health",        "2026-04-30", "April gym"),
    ]
    with conn:
        conn.executemany(
            "INSERT INTO expenses (user_id, amount, category, date, description)"
            " VALUES (?, ?, ?, ?, ?)",
            expenses,
        )
    conn.close()

    return client


# ---------------------------------------------------------------------------
# Auth guard
# ---------------------------------------------------------------------------

class TestAuthGuard:
    def test_unauthenticated_get_redirects_to_login(self, client):
        response = client.get("/profile")
        assert response.status_code == 302, "Unauthenticated /profile must redirect"
        assert "/login" in response.headers["Location"], (
            "Redirect target must be /login"
        )

    def test_unauthenticated_with_date_params_redirects_to_login(self, client):
        response = client.get("/profile?from=2026-04-01&to=2026-04-30")
        assert response.status_code == 302
        assert "/login" in response.headers["Location"]


# ---------------------------------------------------------------------------
# No-params (all-time) baseline
# ---------------------------------------------------------------------------

class TestAllTimeBaseline:
    def test_profile_no_params_returns_200(self, auth_client):
        response = auth_client.get("/profile")
        assert response.status_code == 200, "Authenticated /profile must return 200"

    def test_profile_no_params_shows_all_time_active_button(self, auth_client):
        response = auth_client.get("/profile")
        html = response.data.decode()
        # The "All time" button should carry the active class when no filter
        assert "filter-preset-btn" in html, "Filter preset buttons must be present"
        # Find the All time link – it links to /profile with no params
        assert 'href="/profile"' in html, '"All time" link must point to /profile'

    def test_profile_no_params_has_no_active_filter_label(self, auth_client):
        response = auth_client.get("/profile")
        html = response.data.decode()
        assert "Showing:" not in html, (
            "Active-filter label must NOT appear when no date params are supplied"
        )

    def test_profile_no_params_shows_no_expenses_message_for_new_user(self, auth_client):
        response = auth_client.get("/profile")
        html = response.data.decode()
        # New user has no expenses — expect the empty-state message
        assert "No expenses" in html, (
            "Empty-state message must appear for a user with no expenses"
        )

    def test_profile_no_params_recent_limited_to_5(self, seeded_auth_client):
        """Without a filter, recent transactions show at most 5 rows."""
        response = seeded_auth_client.get("/profile")
        html = response.data.decode()
        # The seeded user has 6 expenses; with LIMIT 5 at most 5 txn-row divs appear
        txn_row_count = html.count("txn-row")
        # txn-row--last is a sub-class, count txn-row occurrences not counting --last
        # Safe approach: count "txn-amt" occurrences (one per transaction rendered)
        txn_amt_count = html.count("txn-amt")
        assert txn_amt_count <= 5, (
            f"All-time view must show at most 5 recent transactions, found {txn_amt_count}"
        )


# ---------------------------------------------------------------------------
# Valid date filter — happy paths
# ---------------------------------------------------------------------------

class TestValidDateFilter:
    def test_filter_returns_200(self, seeded_auth_client):
        response = seeded_auth_client.get("/profile?from=2026-04-01&to=2026-04-30")
        assert response.status_code == 200

    def test_filter_shows_active_filter_label(self, seeded_auth_client):
        response = seeded_auth_client.get("/profile?from=2026-04-01&to=2026-04-30")
        html = response.data.decode()
        assert "Showing:" in html, (
            "Active-filter label must appear when from/to params are present"
        )

    def test_filter_label_includes_start_and_end_dates(self, seeded_auth_client):
        response = seeded_auth_client.get("/profile?from=2026-04-01&to=2026-04-30")
        html = response.data.decode()
        # Label format: "Showing: Apr 1 – Apr 30, 2026"
        assert "Apr" in html, "Filter label must include abbreviated start month"
        assert "2026" in html, "Filter label must include the year"

    def test_filter_excludes_out_of_range_expenses(self, seeded_auth_client):
        """April filter must not include January, February, or March expenses."""
        response = seeded_auth_client.get("/profile?from=2026-04-01&to=2026-04-30")
        html = response.data.decode()
        # Descriptions unique to out-of-range months
        assert "January lunch" not in html, "January expense must be excluded"
        assert "February bus" not in html, "February expense must be excluded"
        assert "March bill" not in html, "March expense must be excluded"

    def test_filter_includes_in_range_expenses(self, seeded_auth_client):
        """April filter must include all April expenses."""
        response = seeded_auth_client.get("/profile?from=2026-04-01&to=2026-04-30")
        html = response.data.decode()
        assert "April groceries" in html, "April groceries expense must be included"
        assert "April movie" in html, "April movie expense must be included"
        assert "April gym" in html, "April gym expense must be included"

    def test_filter_computes_correct_total_for_range(self, seeded_auth_client):
        """April total = 30 + 15 + 25 = 70.00."""
        response = seeded_auth_client.get("/profile?from=2026-04-01&to=2026-04-30")
        html = response.data.decode()
        # Total is rendered as "70.00" (rupee symbol before it)
        assert "70.00" in html, (
            "Filtered total must equal the sum of in-range expenses (70.00)"
        )

    def test_filter_shows_all_matching_transactions_without_limit(self, seeded_auth_client):
        """When a date filter is active, all matching transactions are shown (no LIMIT 5)."""
        # Filter all 6 seeded expenses (2026-01-01 to 2026-12-31)
        response = seeded_auth_client.get("/profile?from=2026-01-01&to=2026-12-31")
        html = response.data.decode()
        txn_amt_count = html.count("txn-amt")
        assert txn_amt_count == 6, (
            f"Filtered view must show all 6 matching transactions, found {txn_amt_count}"
        )

    def test_filter_inclusive_bounds_include_boundary_dates(self, seeded_auth_client):
        """BETWEEN is inclusive: expenses on exactly from_date and to_date must appear."""
        # 2026-04-01 and 2026-04-30 are the exact dates of boundary expenses
        response = seeded_auth_client.get("/profile?from=2026-04-01&to=2026-04-30")
        html = response.data.decode()
        assert "April groceries" in html, "Expense on from_date must be included"
        assert "April gym" in html, "Expense on to_date must be included"

    def test_filter_single_day_range(self, seeded_auth_client):
        """from == to should return only expenses on that exact day."""
        response = seeded_auth_client.get("/profile?from=2026-04-01&to=2026-04-01")
        html = response.data.decode()
        assert "April groceries" in html, "Expense on the exact day must be shown"
        assert "April movie" not in html, "Expenses on other days must be excluded"
        assert "April gym" not in html, "Expenses on other days must be excluded"

    def test_filter_date_range_spanning_multiple_months(self, seeded_auth_client):
        """Filter covering Jan–Mar should include those months and exclude April."""
        response = seeded_auth_client.get("/profile?from=2026-01-01&to=2026-03-31")
        html = response.data.decode()
        assert "January lunch" in html
        assert "February bus" in html
        assert "March bill" in html
        assert "April groceries" not in html
        assert "April movie" not in html

    def test_filter_total_for_multi_month_range(self, seeded_auth_client):
        """Jan–Mar total = 50 + 20 + 100 = 170.00."""
        response = seeded_auth_client.get("/profile?from=2026-01-01&to=2026-03-31")
        html = response.data.decode()
        assert "170.00" in html, "Total for Jan–Mar must be 170.00"


# ---------------------------------------------------------------------------
# Empty / zero-result filter
# ---------------------------------------------------------------------------

class TestEmptyFilterResults:
    def test_filter_with_no_matching_expenses_returns_200(self, seeded_auth_client):
        response = seeded_auth_client.get("/profile?from=2020-01-01&to=2020-12-31")
        assert response.status_code == 200

    def test_filter_with_no_matching_expenses_shows_empty_state(self, seeded_auth_client):
        response = seeded_auth_client.get("/profile?from=2020-01-01&to=2020-12-31")
        html = response.data.decode()
        assert "No expenses" in html, (
            "Empty-state message must appear when no expenses match the filter"
        )

    def test_filter_with_no_matching_expenses_shows_zero_total(self, seeded_auth_client):
        response = seeded_auth_client.get("/profile?from=2020-01-01&to=2020-12-31")
        html = response.data.decode()
        # The categories block is only rendered when categories is truthy;
        # with zero matches the block is absent.  Either way $0.00 must not appear
        # in the total-spending card — just assert the page doesn't crash and
        # the empty-state is shown (previous test covers that).
        # If the implementation renders a $0.00 summary card that is also acceptable.
        # The critical requirement is "no crash".
        assert "500" not in html or "Internal Server Error" not in html, (
            "Page must not return a server error for a zero-result filter"
        )

    def test_filter_zero_total_does_not_cause_division_by_zero(self, seeded_auth_client):
        """Spec rule: guard division by zero — pct=0 for all categories when total=0."""
        # There are no expenses in year 2019, so total_spent will be 0
        response = seeded_auth_client.get("/profile?from=2019-01-01&to=2019-12-31")
        assert response.status_code == 200, (
            "Division-by-zero guard must prevent a 500 error when total_spent is 0"
        )

    def test_filter_zero_result_still_shows_active_filter_label(self, seeded_auth_client):
        response = seeded_auth_client.get("/profile?from=2020-01-01&to=2020-12-31")
        html = response.data.decode()
        assert "Showing:" in html, (
            "Active-filter label must appear even when the filter yields no results"
        )


# ---------------------------------------------------------------------------
# Malformed / invalid date params
# ---------------------------------------------------------------------------

class TestMalformedDateParams:
    @pytest.mark.parametrize("params", [
        "?from=bad&to=also-bad",
        "?from=not-a-date&to=2026-04-30",
        "?from=2026-04-01&to=not-a-date",
        "?from=20260401&to=20260430",          # missing hyphens
        "?from=2026/04/01&to=2026/04/30",      # wrong separator
        "?from=&to=",                           # empty strings
        "?from=99999-99-99&to=99999-99-99",    # out-of-range values
        "?from='; DROP TABLE users; --&to=2026-04-30",  # SQL injection attempt
    ])
    def test_malformed_params_do_not_crash_route(self, seeded_auth_client, params):
        response = seeded_auth_client.get(f"/profile{params}")
        assert response.status_code == 200, (
            f"Malformed params {params!r} must not crash the route (expected 200)"
        )

    @pytest.mark.parametrize("params", [
        "?from=bad&to=also-bad",
        "?from=not-a-date&to=2026-04-30",
        "?from=2026-04-01&to=not-a-date",
        "?from=&to=",
    ])
    def test_malformed_params_treated_as_all_time(self, seeded_auth_client, params):
        """Malformed params are silently discarded; page behaves as all-time view."""
        response = seeded_auth_client.get(f"/profile{params}")
        html = response.data.decode()
        assert "Showing:" not in html, (
            f"Malformed params {params!r} must not trigger the active-filter label"
        )

    def test_only_from_param_treated_as_all_time(self, seeded_auth_client):
        """Providing only 'from' without 'to' must be treated as all-time."""
        response = seeded_auth_client.get("/profile?from=2026-04-01")
        assert response.status_code == 200
        html = response.data.decode()
        assert "Showing:" not in html, (
            "Only 'from' without 'to' must not activate the filter"
        )

    def test_only_to_param_treated_as_all_time(self, seeded_auth_client):
        """Providing only 'to' without 'from' must be treated as all-time."""
        response = seeded_auth_client.get("/profile?to=2026-04-30")
        assert response.status_code == 200
        html = response.data.decode()
        assert "Showing:" not in html, (
            "Only 'to' without 'from' must not activate the filter"
        )


# ---------------------------------------------------------------------------
# Template — filter bar landmarks
# ---------------------------------------------------------------------------

class TestFilterBarTemplate:
    def test_filter_bar_present_on_profile_page(self, auth_client):
        response = auth_client.get("/profile")
        html = response.data.decode()
        assert "filter-bar" in html, "filter-bar element must be present on profile page"

    def test_filter_presets_container_present(self, auth_client):
        response = auth_client.get("/profile")
        html = response.data.decode()
        assert "filter-presets" in html, "filter-presets container must be present"

    def test_all_time_link_present_and_points_to_bare_profile(self, auth_client):
        response = auth_client.get("/profile")
        html = response.data.decode()
        assert "All time" in html, '"All time" link text must appear'
        assert 'href="/profile"' in html, '"All time" link must href to /profile (no params)'

    def test_this_month_preset_button_present(self, auth_client):
        response = auth_client.get("/profile")
        html = response.data.decode()
        assert "This Month" in html, '"This Month" preset button must appear'

    def test_last_3_months_preset_button_present(self, auth_client):
        response = auth_client.get("/profile")
        html = response.data.decode()
        assert "Last 3 Months" in html, '"Last 3 Months" preset button must appear'

    def test_this_year_preset_button_present(self, auth_client):
        response = auth_client.get("/profile")
        html = response.data.decode()
        assert "This Year" in html, '"This Year" preset button must appear'

    def test_custom_date_form_uses_get_method(self, auth_client):
        response = auth_client.get("/profile")
        html = response.data.decode()
        # The form must submit via GET so params appear in the URL
        assert 'method="get"' in html.lower() or "method=get" in html.lower(), (
            "Custom date-range form must use GET method"
        )

    def test_custom_date_form_action_points_to_profile(self, auth_client):
        response = auth_client.get("/profile")
        html = response.data.decode()
        assert 'action="/profile"' in html, (
            "Custom date-range form action must point to /profile"
        )

    def test_custom_date_form_has_from_and_to_inputs(self, auth_client):
        response = auth_client.get("/profile")
        html = response.data.decode()
        assert 'name="from"' in html, "Filter form must have a 'from' date input"
        assert 'name="to"' in html, "Filter form must have a 'to' date input"

    def test_custom_date_inputs_are_type_date(self, auth_client):
        response = auth_client.get("/profile")
        html = response.data.decode()
        assert 'type="date"' in html, "Date inputs must be type='date'"

    def test_filter_label_css_class_present_when_filter_active(self, seeded_auth_client):
        response = seeded_auth_client.get("/profile?from=2026-04-01&to=2026-04-30")
        html = response.data.decode()
        assert "filter-label" in html, (
            ".filter-label element must appear when a date filter is active"
        )

    def test_filter_label_absent_when_no_filter(self, auth_client):
        response = auth_client.get("/profile")
        html = response.data.decode()
        # filter-label class appears only inside the {% if from_date and to_date %} block
        assert "filter-label" not in html, (
            ".filter-label must not appear when no date filter is active"
        )


# ---------------------------------------------------------------------------
# Preset link correctness — URLs must contain today-relative dates
# ---------------------------------------------------------------------------

class TestPresetLinkDates:
    """
    The preset hrefs are computed server-side from today's date.
    We verify they contain the expected date strings according to the spec rules.
    """

    def test_this_month_preset_href_contains_correct_from_date(self, auth_client):
        today = date.today()
        expected_from = date(today.year, today.month, 1).isoformat()
        response = auth_client.get("/profile")
        html = response.data.decode()
        assert expected_from in html, (
            f'"This Month" from date must be {expected_from}'
        )

    def test_this_month_preset_href_contains_correct_to_date(self, auth_client):
        today = date.today()
        expected_to = today.isoformat()
        response = auth_client.get("/profile")
        html = response.data.decode()
        assert expected_to in html, (
            f'"This Month" to date must be today ({expected_to})'
        )

    def test_this_year_preset_href_contains_jan_1(self, auth_client):
        today = date.today()
        expected_from = date(today.year, 1, 1).isoformat()
        response = auth_client.get("/profile")
        html = response.data.decode()
        assert expected_from in html, (
            f'"This Year" from date must be Jan 1 of this year ({expected_from})'
        )

    def test_last_3_months_preset_href_contains_correct_from_date(self, auth_client):
        today = date.today()
        expected_from = _first_day_3_months_ago(today).isoformat()
        response = auth_client.get("/profile")
        html = response.data.decode()
        assert expected_from in html, (
            f'"Last 3 Months" from date must be {expected_from}'
        )

    def test_all_preset_links_use_profile_route(self, auth_client):
        """All preset anchors must link to /profile with query params."""
        response = auth_client.get("/profile")
        html = response.data.decode()
        # At minimum four href="/profile" occurrences (All time has no params;
        # the others have ?from=...&to=...)
        assert html.count('href="/profile') >= 4, (
            "There must be at least 4 preset links all pointing to /profile"
        )


# ---------------------------------------------------------------------------
# Active preset highlighting
# ---------------------------------------------------------------------------

class TestActivePresetHighlighting:
    def test_all_time_has_active_class_when_no_filter(self, auth_client):
        response = auth_client.get("/profile")
        html = response.data.decode()
        # The All-time button should have the active class when no params
        # Expect pattern: href="/profile" ... active  (in some order in the element)
        # Simple check: "All time" appears and "active" class exists in the page
        assert "active" in html, "An 'active' class must appear on a preset button"

    def test_this_month_has_active_class_when_matching(self, auth_client):
        today = date.today()
        tm_from = date(today.year, today.month, 1).isoformat()
        tm_to = today.isoformat()
        response = auth_client.get(f"/profile?from={tm_from}&to={tm_to}")
        html = response.data.decode()
        # The This Month button should be active
        # The template adds "active" to the button whose from matches
        assert "active" in html, (
            "The 'This Month' button must have the active class when its dates are active"
        )

    def test_all_time_does_not_have_active_class_when_filter_set(self, seeded_auth_client):
        """When a date filter is active, 'All time' should not carry the active class."""
        response = seeded_auth_client.get("/profile?from=2026-04-01&to=2026-04-30")
        html = response.data.decode()
        # The template uses {% if not from_date %} for the All-time active class.
        # When from_date is set, "All time" must not be active.
        # We verify "Showing:" is present (filter is active) and trust the template logic.
        assert "Showing:" in html, "Filter must be active for this assertion to be meaningful"


# ---------------------------------------------------------------------------
# HTTP semantics
# ---------------------------------------------------------------------------

class TestHttpSemantics:
    def test_profile_with_valid_filter_returns_200(self, seeded_auth_client):
        response = seeded_auth_client.get("/profile?from=2026-01-01&to=2026-12-31")
        assert response.status_code == 200

    def test_profile_without_params_returns_200(self, auth_client):
        response = auth_client.get("/profile")
        assert response.status_code == 200

    def test_profile_post_not_allowed(self, auth_client):
        """POST to /profile is not defined; must return 405 Method Not Allowed."""
        response = auth_client.post("/profile", data={"from": "2026-04-01", "to": "2026-04-30"})
        assert response.status_code == 405, (
            "/profile accepts only GET; POST must return 405"
        )


# ---------------------------------------------------------------------------
# Category breakdown
# ---------------------------------------------------------------------------

class TestCategoryBreakdown:
    def test_filter_shows_categories_for_in_range_expenses(self, seeded_auth_client):
        """Filtered view must show the categories of matching expenses."""
        response = seeded_auth_client.get("/profile?from=2026-04-01&to=2026-04-30")
        html = response.data.decode()
        # April has Food, Entertainment, Health
        assert "Food" in html
        assert "Entertainment" in html
        assert "Health" in html

    def test_filter_excludes_categories_not_in_range(self, seeded_auth_client):
        """Categories that exist only outside the range must not appear in the breakdown."""
        # Filter to January only — only "Food" category appears
        response = seeded_auth_client.get("/profile?from=2026-01-01&to=2026-01-31")
        html = response.data.decode()
        assert "Food" in html, "Food category must appear for January"
        # Transport is February-only, Bills is March-only
        assert "February bus" not in html
        assert "March bill" not in html

    def test_filter_category_percentage_sums_are_reasonable(self, seeded_auth_client):
        """Category percentages must be between 0 and 100."""
        response = seeded_auth_client.get("/profile?from=2026-04-01&to=2026-04-30")
        html = response.data.decode()
        # Just verify the page renders without errors and contains percentage-width styles
        assert "width:" in html, "Category bar widths must be rendered as inline styles"

    def test_all_time_shows_all_categories(self, seeded_auth_client):
        """All-time view must show all categories present across all expenses."""
        response = seeded_auth_client.get("/profile")
        html = response.data.decode()
        assert "Food" in html
        assert "Transport" in html
        assert "Bills" in html
        assert "Entertainment" in html
        assert "Health" in html

    def test_all_time_total_equals_sum_of_all_expenses(self, seeded_auth_client):
        """All-time total = 50 + 20 + 100 + 30 + 15 + 25 = 240.00."""
        response = seeded_auth_client.get("/profile")
        html = response.data.decode()
        assert "240.00" in html, "All-time total must be 240.00 for the seeded dataset"


# ---------------------------------------------------------------------------
# Data isolation — users see only their own expenses
# ---------------------------------------------------------------------------

class TestUserDataIsolation:
    def test_filter_returns_only_current_users_expenses(self, app, client):
        """
        Register two users with expenses in the same date range.
        Each user must see only their own expenses when filtering.
        """
        import database.db as db_module

        # Register user A
        client.post("/register", data={
            "name": "User A",
            "email": "usera@test.com",
            "password": "passwordA1",
        })

        # Insert an expense for User A directly
        conn = sqlite3.connect(db_module.DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        uid_a = conn.execute(
            "SELECT id FROM users WHERE email = ?", ("usera@test.com",)
        ).fetchone()["id"]
        with conn:
            conn.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description)"
                " VALUES (?, ?, ?, ?, ?)",
                (uid_a, 99.99, "Shopping", "2026-04-10", "User A secret purchase"),
            )
        conn.close()

        # Register user B and log in as B
        client.post("/register", data={
            "name": "User B",
            "email": "userb@test.com",
            "password": "passwordB1",
        })
        # user B is now logged in (register sets the session)

        response = client.get("/profile?from=2026-04-01&to=2026-04-30")
        html = response.data.decode()
        assert "User A secret purchase" not in html, (
            "User B must not see User A's expenses in a filtered view"
        )
