import os
from decimal import Decimal, InvalidOperation
from flask import Flask, render_template, request, redirect, url_for, session, abort
from werkzeug.security import generate_password_hash, check_password_hash
from database.db import get_db, init_db, seed_db
from datetime import datetime, date
import sqlite3

EXPENSE_CATEGORIES = ["Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other"]

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "spendly-dev-secret")

with app.app_context():
    init_db()
    seed_db()


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not name or not email or not password:
            return render_template("register.html", error="All fields are required.", name=name, email=email)

        if len(password) < 8:
            return render_template("register.html", error="Password must be at least 8 characters.", name=name, email=email)

        db = get_db()
        try:
            db.execute(
                "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password)),
            )
            db.commit()
        except sqlite3.IntegrityError:
            return render_template("register.html", error="An account with that email already exists.", name=name, email=email)

        user = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        session["user_id"] = user["id"]
        session["user_name"] = name
        return redirect(url_for("landing"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        if not email or not password:
            return render_template("login.html", error="All fields are required.", email=email)

        db = get_db()
        user = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            return render_template("login.html", error="Invalid email or password.", email=email)

        session["user_id"] = user["id"]
        session["user_name"] = user["name"]
        return redirect(url_for("landing"))

    return render_template("login.html")


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


def _build_date_presets(today):
    m3_month = today.month - 2
    m3_year  = today.year
    if m3_month <= 0:
        m3_month += 12
        m3_year  -= 1
    return {
        "this_month":    {"from": date(today.year, today.month, 1).isoformat(), "to": today.isoformat()},
        "last_3_months": {"from": date(m3_year, m3_month, 1).isoformat(),       "to": today.isoformat()},
        "this_year":     {"from": date(today.year, 1, 1).isoformat(),            "to": today.isoformat()},
    }


@app.route("/profile")
def profile():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    uid = session["user_id"]
    db = get_db()
    user = db.execute(
        "SELECT name, email, created_at FROM users WHERE id = ?",
        (uid,)
    ).fetchone()

    if user is None:
        session.clear()
        return redirect(url_for("login"))

    member_since = datetime.strptime(user["created_at"][:10], "%Y-%m-%d").strftime("%B %Y")

    from_raw  = request.args.get("from", "")
    to_raw    = request.args.get("to", "")
    from_date = to_date = None
    try:
        if from_raw and to_raw:
            from_date = datetime.strptime(from_raw, "%Y-%m-%d").date()
            to_date   = datetime.strptime(to_raw,   "%Y-%m-%d").date()
            if from_date > to_date:
                from_date = to_date = None
    except ValueError:
        pass

    presets = _build_date_presets(date.today())

    if from_date and to_date:
        fd, td = from_date.isoformat(), to_date.isoformat()

        total_spent = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses"
            " WHERE user_id = ? AND date BETWEEN ? AND ?",
            (uid, fd, td),
        ).fetchone()[0]

        cat_rows = db.execute(
            "SELECT category, SUM(amount) as total FROM expenses"
            " WHERE user_id = ? AND date BETWEEN ? AND ?"
            " GROUP BY category ORDER BY total DESC",
            (uid, fd, td),
        ).fetchall()

        recent = db.execute(
            "SELECT id, amount, category, date, description FROM expenses"
            " WHERE user_id = ? AND date BETWEEN ? AND ?"
            " ORDER BY date DESC",
            (uid, fd, td),
        ).fetchall()
    else:
        total_spent = db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses WHERE user_id = ?",
            (uid,),
        ).fetchone()[0]

        cat_rows = db.execute(
            "SELECT category, SUM(amount) as total FROM expenses"
            " WHERE user_id = ? GROUP BY category ORDER BY total DESC",
            (uid,),
        ).fetchall()

        recent = db.execute(
            "SELECT id, amount, category, date, description FROM expenses"
            " WHERE user_id = ? ORDER BY date DESC LIMIT 5",
            (uid,),
        ).fetchall()

    categories = [
        {
            "name": r["category"],
            "total": r["total"],
            "pct": round(r["total"] / total_spent * 100) if total_spent else 0,
        }
        for r in cat_rows
    ]

    return render_template("profile.html",
        user=user,
        member_since=member_since,
        total_spent=total_spent,
        categories=categories,
        recent=recent,
        from_date=from_date,
        to_date=to_date,
        presets=presets,
    )


@app.route("/analytics")
def analytics():
    if not session.get("user_id"):
        return redirect(url_for("login"))
    return render_template("analytics.html")


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    if not session.get("user_id"):
        return redirect(url_for("login"))

    form = {}
    error = None

    if request.method == "POST":
        form = {
            "amount":      request.form.get("amount", "").strip(),
            "category":    request.form.get("category", "").strip(),
            "date":        request.form.get("date", "").strip(),
            "description": request.form.get("description", "").strip(),
        }

        try:
            amount = Decimal(form["amount"])
            if amount <= 0:
                raise InvalidOperation
        except InvalidOperation:
            error = "Amount must be a positive number."

        if not error and form["category"] not in EXPENSE_CATEGORIES:
            error = "Please select a valid category."

        if not error:
            try:
                datetime.strptime(form["date"], "%Y-%m-%d")
            except ValueError:
                error = "Please enter a valid date."

        if not error and len(form["description"]) > 200:
            error = "Description must be 200 characters or fewer."

        if not error:
            db = get_db()
            db.execute(
                "INSERT INTO expenses (user_id, amount, category, date, description) VALUES (?, ?, ?, ?, ?)",
                (session["user_id"], str(amount), form["category"], form["date"], form["description"] or None),
            )
            db.commit()
            return redirect(url_for("profile"))

    return render_template("add_expense.html",
        categories=EXPENSE_CATEGORIES,
        error=error,
        date=form.get("date") or date.today().isoformat(),
        amount=form.get("amount", ""),
        category=form.get("category", ""),
        description=form.get("description", ""),
    )


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    db = get_db()
    expense = db.execute(
        "SELECT * FROM expenses WHERE id = ?", (id,)
    ).fetchone()

    if expense is None or expense["user_id"] != session["user_id"]:
        abort(404)

    form = {}
    error = None

    if request.method == "POST":
        form = {
            "amount":      request.form.get("amount", "").strip(),
            "category":    request.form.get("category", "").strip(),
            "date":        request.form.get("date", "").strip(),
            "description": request.form.get("description", "").strip(),
        }

        try:
            amount = Decimal(form["amount"])
            if amount <= 0:
                raise InvalidOperation
        except InvalidOperation:
            error = "Amount must be a positive number."

        if not error and form["category"] not in EXPENSE_CATEGORIES:
            error = "Please select a valid category."

        if not error:
            try:
                datetime.strptime(form["date"], "%Y-%m-%d")
            except ValueError:
                error = "Please enter a valid date."

        if not error and len(form["description"]) > 200:
            error = "Description must be 200 characters or fewer."

        if not error:
            db.execute(
                "UPDATE expenses SET amount=?, category=?, date=?, description=?"
                " WHERE id=? AND user_id=?",
                (str(amount), form["category"], form["date"],
                 form["description"] or None, id, session["user_id"]),
            )
            db.commit()
            return redirect(url_for("profile"))

    return render_template("edit_expense.html",
        categories=EXPENSE_CATEGORIES,
        error=error,
        expense_id=id,
        amount=form.get("amount") if form else expense["amount"],
        category=form.get("category") if form else expense["category"],
        date=form.get("date") if form else expense["date"],
        description=form.get("description") if form else (expense["description"] or ""),
    )


@app.route("/expenses/<int:id>/delete", methods=["POST"])
def delete_expense(id):
    if not session.get("user_id"):
        return redirect(url_for("login"))

    db = get_db()
    result = db.execute(
        "DELETE FROM expenses WHERE id = ? AND user_id = ?",
        (id, session["user_id"]),
    )
    db.commit()

    if result.rowcount == 0:
        abort(404)

    return redirect(url_for("profile"))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
