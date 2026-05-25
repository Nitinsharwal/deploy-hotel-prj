# Noma — Hotel Booking Platform

A production-grade hotel booking platform built with Django 4.2.  Customers
discover stays, vendors manage their inventory, and a super-admin operates the
business — all in one cohesive web app.

[![Tests](https://img.shields.io/badge/tests-38_passing-brightgreen)]() [![Python 3.12](https://img.shields.io/badge/python-3.12-blue)]() [![Django 4.2](https://img.shields.io/badge/django-4.2-darkgreen)]()

---

## What it does

**For guests**
- Search hotels by location, dates, price, amenities, rating
- Book rooms with availability + capacity enforcement at the DB level
- Pay via a demo checkout (Razorpay code is in place; toggle when ready)
- Get a confirmation slip in their inbox + a printable PDF-ready receipt page
- Manage every booking from a personal profile hub — upcoming, past, cancelled
- Cancel before check-in (auto-refund when a real gateway is wired)
- Review a hotel once the stay is completed — gated to verified guests only

**For vendors**
- Register + email-verify, list multiple hotels and rooms
- Bulk-upload photos with drag-and-drop, see all bookings per hotel
- Receive platform charges (publishing fee / monthly subscription / boost),
  pay them inline, see payment history
- Get email reminders 5 days before due and through the grace period

**For super-admins**
- Branded private dashboard at `/super-admin/` (404s for anyone else)
- Verify vendors, levy platform charges (per-hotel or account-wide),
  set due dates + grace periods, edit / mark paid / waive
- Logging in requires an OTP delivered to the registered email (2FA)

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Django 4.2, PostgreSQL 16 (SQLite in tests) |
| Auth | Django auth + `django-allauth` (Google OAuth) + `django-axes` (brute-force lockout) + custom email-OTP for super-admin |
| Payments | Razorpay (test mode), wrapped in a demo-mode shim — flip a flag to go live |
| Frontend | Server-rendered Django templates + a single hand-tuned mobile-first stylesheet (no JS framework) |
| Background jobs | Django management commands invoked by cron (no Celery dependency) |
| Email | SMTP (Gmail app password in dev), table-based HTML templates that render in Gmail / Apple Mail / Outlook |
| Tests | pytest + pytest-django, 38 tests, in-memory SQLite |
| Deploy | Render / Vercel ready; WhiteNoise for static; safe-area-inset CSS for notched phones |

---

## Quick start

```bash
# 1. Clone + virtualenv
git clone <your-fork-url>
cd deploy-hotel-prj
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure secrets
cp .env.example .env
# Edit .env — at minimum set: SECRET_KEY, DATABASE_URL, EMAIL_*

# 3. Database
createdb hotel_DB
python manage.py migrate
python manage.py createsuperuser

# 4. Run
python manage.py runserver
# → http://127.0.0.1:8000/
```

## Required environment variables

See [`.env.example`](.env.example) for the full list. At a glance:

| Variable | Purpose |
|---|---|
| `SECRET_KEY` | Django secret — fail-fast if missing |
| `DEBUG` | `True` locally, `False` in prod |
| `ALLOWED_HOSTS` | comma-separated host list |
| `DATABASE_URL` | `postgresql://user:pw@host:port/db` |
| `EMAIL_USER`, `EMAIL_PASSWORD` | SMTP credentials |
| `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` | gateway (test mode in dev) |
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | "Continue with Google" |
| `SITE_URL` | absolute URL used in email links |

---

## Running the test suite

```bash
pytest                        # ~25 tests, ~30 seconds
pytest --cov=. --cov-report=term-missing   # with coverage
python manage.py check        # static system check
```

The test config in [`conftest.py`](conftest.py) forces an in-memory SQLite + disables axes
so tests are deterministic regardless of your local `.env`.

---

## Operational commands

```bash
# Mark past bookings as completed (daily cron)
python manage.py complete_past_bookings

# Email vendors about pending charges in the reminder window (daily cron)
python manage.py send_charge_reminders --dry-run   # preview first
python manage.py send_charge_reminders             # send for real
```

**Suggested cron:**
```cron
0 1 * * * cd /app && python manage.py complete_past_bookings
0 9 * * * cd /app && python manage.py send_charge_reminders
```

---

## Architecture notes

- **Two profile models** — `hotel_owner` (customers) and `hotel_vendor` (sellers) hang
  off `auth.User` via `OneToOneField`. Lets each role have role-specific fields
  without polluting `User`.
- **Booking state machine** — `PENDING → CONFIRMED → COMPLETED` (or `CANCELLED`).
  Transitions guarded by `Booking.cancel()` and the `complete_past_bookings`
  management command. A `CheckConstraint` enforces `end_date > start_date` at DB level.
- **Room availability** — computed live: `Room.is_available(start, end)` counts
  overlapping non-cancelled bookings against `total_count`. No availability cache
  to invalidate, no race conditions.
- **Payment as a separate model** — many payments per booking (initial attempt,
  retry, refund), each with a status. The `transaction_id` is the gateway's
  reference for audit / dispute resolution.
- **Reviews tied to bookings** — `Review` has a OneToOne on `Booking`, so a guest
  can only review a stay they actually had. The Booking must be `COMPLETED`.
- **Vendor charges with grace periods** — overdue vendors' hotels disappear from
  public listings via `_blocked_vendor_ids()`. Vendor sees them in their dashboard
  with a red banner.
- **Super-admin 2FA** — superuser passwords alone don't grant access; a 6-digit
  OTP emailed to the registered address gates `/super-admin/`. Session-based,
  10-min expiry, 5-attempt limit.

---

## Project layout

```
deploy-hotel-prj/
├── hotel_prj/              # Django project (settings, root urls, wsgi)
├── accounts/               # Auth, profiles, vendor CRUD, super-admin
│   ├── models.py           # User profiles + business models
│   ├── views.py            # Customer auth + vendor flows
│   ├── super_admin.py      # /super-admin/ views (404 for non-superusers)
│   ├── management/commands/    # cron jobs
│   └── templates/
├── hotel_app/              # Customer-facing site + booking flow
│   ├── views.py            # Home, hotel detail, booking, payment, reviews
│   ├── forms.py            # ModelForms with availability + capacity validation
│   ├── payments.py         # Razorpay (real) + demo shim
│   └── templates/
└── conftest.py             # pytest fixtures (forces SQLite + disables axes)
```

---

## Going to production

1. Set `DEBUG=False` and `ALLOWED_HOSTS` to your real domain
2. Generate a fresh `SECRET_KEY` and put it in your host's secrets manager
3. Apply migrations on the production DB
4. Wire `python manage.py collectstatic --noinput` into your build step
5. Add the two cron jobs above
6. Toggle from demo payments to real Razorpay (uncomment `payment_verify` +
   `razorpay_webhook` in `hotel_app/views.py`, restore the routes)
7. Add a real OAuth redirect URI in Google Cloud Console for your prod domain

---

## Caching & CDN

The project ships with three caching layers, all opt-in but pre-wired:

### 1. Application cache (Redis or LocMem)

`hotel_app/views.py` caches two things:

| What | Key | TTL | Invalidated by |
|---|---|---|---|
| Set of blocked vendor ids (overdue charges) | `blocked_vendor_ids` | 5 min | `VendorCharge` save/delete signal |
| Home page hotel grid (per filter combo) | `home_hotels:vN:<hash>` | 1 min | `Hotel` / `Review` / `VendorCharge` save/delete |

Backend selection happens automatically in `settings.py`:

- **`REDIS_URL` set** → uses Django's built-in `RedisCache`. Recommended in prod
  because gunicorn workers share state.
- **`REDIS_URL` empty** → `LocMemCache`. Per-process, zero setup, fine for dev.

Cheap managed Redis options: [Upstash](https://upstash.com) (free 10k req/day),
[Redis Cloud](https://redis.com/try-free/) free tier, or `apt install redis-server`
on a small VM (~2 MB RAM for our usage).

```env
# .env in production
REDIS_URL=rediss://default:PASSWORD@host.upstash.io:6380/0?ssl_cert_reqs=required
```

### 2. HTTP cache headers

- **`/static/`** → WhiteNoise stamps `Cache-Control: public, max-age=31536000, immutable`
  because every static file has a content hash in its name (cache forever, safe).
- **`/media/`** → `MediaCacheMiddleware` stamps `Cache-Control: public, max-age=86400, immutable`
  (1 day). User-uploaded hotel images rarely change.

This means a CDN in front of your domain will serve those URLs from edge cache
without ever asking Django.

### 3. CDN in front (recommended: Cloudflare, free tier)

Put a CDN in front of your domain and it will respect the `Cache-Control` headers
above and cache `/static/` + `/media/` globally on its edge network. First visitor
in each region warms the cache; everyone else gets ~20 ms responses for assets.

**Cloudflare setup** (5 minutes):

1. Sign up at [cloudflare.com](https://cloudflare.com), add your domain
2. Cloudflare gives you 2 nameservers — set them at your DNS registrar
3. In Cloudflare → SSL/TLS → set mode to **Full (strict)**
4. Cloudflare → Caching → Configuration → enable **Always Online**
5. Cloudflare → Rules → Page Rules → add:
   - URL pattern: `yourdomain.com/static/*` → Cache Level: **Cache Everything**, Edge Cache TTL: **1 month**
   - URL pattern: `yourdomain.com/media/*` → Cache Level: **Cache Everything**, Edge Cache TTL: **1 day**
6. (Optional) Cloudflare → Speed → Optimization → enable Brotli + Auto Minify

Now your static CSS/JS and hotel images are served from 300+ edge locations
globally with no extra config on the Django side. First view from a new region
hits your server once, then everyone in that region gets it from Cloudflare.

Verify it's working: `curl -I https://yourdomain.com/static/hotel_app/css/style.css`
should show `cf-cache-status: HIT` after the second request.

### Alternative: Bunny.net / CloudFront / Fastly

Any CDN works — they all read the `Cache-Control` header. Just point the CDN at
your origin domain. Bunny.net is very cheap at scale (~$0.01/GB).

---

## License

MIT — use it, fork it, ship it.
