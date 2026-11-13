# Vidyamarga - Path of Knowledge

A Flask + SQLite web platform that lets students in Standards 1-10 discover competitive
examinations, check eligibility, and access study notes (free or paid).

## Quick start (Windows, macOS, Linux)

Requires Python 3.10 or newer.

```bash
cd vidyamarga
python -m venv .venv
# Windows:  .venv\Scripts\activate        macOS/Linux:  source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env            # Windows: copy .env.example .env
# edit .env and set SECRET_KEY to a long random string

flask --app run init-db         # creates instance/vidyamarga.db
flask --app run create-admin    # asks for name, email, password
flask --app run seed            # optional: SAMPLE exams, rules and notes
python run.py                   # http://127.0.0.1:5000
```

* Students register at `/auth/register`.
* Administrators log in at `/auth/admin/login` (no public admin sign-up; create them with the CLI).

## Run the tests

```bash
python -m unittest discover -s tests -t .
```

77 tests cover authentication and roles, CSRF, the eligibility engine, note access
(paid notes locked until payment is confirmed), payment tampering/replay/underpayment,
Razorpay signature and webhook handling, admin CRUD and upload validation.

## Payments

The server never trusts the browser for money. The price is read from the `notes` table,
the order is created server-side, and an order becomes `paid` only when
`app/services/payments/service.py` receives a result the provider driver has verified.

| Mode | Setup | Use for |
|---|---|---|
| `mock` (default) | none | Offline demos. A local "gateway" page signs the result with a server-only secret; forged or altered results fail verification. |
| `razorpay` | Razorpay **test** keys in `.env`, `PAYMENT_PROVIDER=razorpay` | Realistic sandbox. Checks the HMAC signature, then asks Razorpay's API to confirm order id, status and amount. |

For Razorpay webhooks add `https://<your-host>/payments/webhook/razorpay` in the Razorpay
dashboard and put its secret in `RAZORPAY_WEBHOOK_SECRET` (local testing needs a tunnel such as ngrok).
Set `ALLOW_MOCK_PAYMENTS=0` in any shared deployment.

## Project layout

```
run.py  config.py  (CLI commands live in app/cli.py)
app/
  __init__.py         app factory, error handlers
  db.py  schema.sql   SQLite connection + all tables
  security.py         CSRF, session user, login throttle, security headers
  validators.py       server-side validation of every form
  models/             SQL for each table (user, examination, eligibility, note, order, bookmark, audit)
  auth/               login, register, admin login, decorators
  services/           eligibility_engine, note_access, uploads, payments/{mock,razorpay,service}
  routes/             main, exams, bookmarks, notes, payments, admin
  templates/ static/  Jinja pages, CSS, small JS files
tests/                unittest suite
instance/             database + protected_notes/ (never served directly)
```

## Security summary

Password hashing (Werkzeug), session fixation protection, CSRF on every POST, login
throttling, role checks on the server for admin routes, private note storage with
authorised download, upload allow-list + content check + random file names, parameterised SQL
only, strict Content-Security-Policy and other headers, safe `next` redirects.

## Know before you present or deploy

* **Seed data is illustrative.** Dates are generated relative to today and eligibility is
  simplified. Replace it with verified data from official notices; the UI labels sample
  records and shows when a link was last checked.
* Login throttling is per process (in memory). Use a shared store if you run several workers.
* The Razorpay driver is covered by unit tests with a faked HTTP layer; test it once against
  your own Razorpay test account before relying on it.
* For real hosting: `VIDYAMARGA_ENV=production`, a strong `SECRET_KEY`, HTTPS with
  `SESSION_COOKIE_SECURE=1`, and a production server such as `gunicorn "run:app"` (Linux) or `waitress` (Windows).
* Passwords cannot be reset by email yet (out of scope for the prototype).
