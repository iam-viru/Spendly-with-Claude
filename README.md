# Spendly — Track Every Rupee

**Spendly** is a clean, no-fuss personal expense tracker built with Flask. Log your expenses, understand your spending patterns, and stay on top of your budget — without the spreadsheet headache.

> Live demo → [spendly Live URL](https://spendly-production-b32a.up.railway.app/) 

---

## Features

- **Register & log in** — secure accounts with hashed passwords
- **Add expenses** — amount, category, date, and an optional description
- **Edit & delete** — update or remove any expense at any time
- **Spending dashboard** — total spent, per-category breakdown with percentages
- **Date filtering** — view by this month, last 3 months, this year, or a custom range
- **7 categories** — Food, Transport, Bills, Health, Entertainment, Shopping, Other

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3 · Flask |
| Database | SQLite (raw SQL, no ORM) |
| Auth | Flask sessions · Werkzeug password hashing |
| Frontend | Jinja2 templates · Vanilla JS · CSS custom properties |
| Server | Gunicorn |
| Hosting | Railway |

---

## Getting Started (Local)

### 1. Clone the repo

```bash
git clone https://github.com/iam-viru/Spendly-with-Claude.git
cd Spendly-with-Claude
```

### 2. Create a virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
python app.py
```

Open [http://localhost:5001](http://localhost:5001) in your browser.

The database is created automatically on first run, and a demo account is seeded:

| Field | Value |
|---|---|
| Email | `demo@spendly.com` |
| Password | `demo123` |

---

## Project Structure

```
spendly/
├── app.py               # All routes and app config
├── database/
│   └── db.py            # SQLite helpers (get_db, init_db, seed_db)
├── templates/           # Jinja2 HTML templates
│   ├── base.html        # Shared layout (navbar, footer)
│   ├── landing.html
│   ├── login.html
│   ├── register.html
│   ├── profile.html     # Spending dashboard
│   ├── add_expense.html
│   ├── edit_expense.html
│   ├── analytics.html
│   ├── terms.html
│   └── privacy.html
├── static/
│   ├── css/style.css    # Single stylesheet with CSS variables
│   └── js/main.js       # Vanilla JS (video modal)
├── requirements.txt
└── Procfile             # For Railway / Heroku deployment
```

---

## Running Tests

```bash
pytest
```

Run a specific test file:

```bash
pytest tests/test_auth.py
```

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | `spendly-dev-secret` | Flask session secret — **change this in production** |

Set it on Railway under **Variables** in your service settings.

---

## Deploying to Railway

1. Push your code to GitHub
2. Create a new Railway project and connect your GitHub repo
3. Set the `SECRET_KEY` environment variable to a long random string
4. Railway detects the `Procfile` and deploys automatically

---

## License

MIT — free to use, modify, and distribute and do not forget to give credit.
