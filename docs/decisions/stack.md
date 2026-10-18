# Stack

Status: decided by Akhil, 2026-10-18. Issues: #2, #3.

## North Star

The fewest moving parts that meet the brief: a Django API that composes third-party providers and a
pure risk engine, and a browser app that renders routes and a 48-hour corridor smoothly. Every part
must run with one command locally and as plain containers on a single small VM.

Out of scope: user accounts, saved trips, background jobs.

## Backend

### D1. Django 5.2 LTS with Django REST Framework and drf-spectacular
The brief names Django. DRF is the standard way to build typed JSON APIs on it, and drf-spectacular
generates an OpenAPI 3 schema from the serializers, which the frontend turns into TypeScript types.
One schema then defines the contract on both sides.
5.2 is the current LTS (security fixes to April 2028), and DRF, drf-spectacular and pytest-django all
list it as supported.
Rejected: Django 6.1, because drf-spectacular and pytest-django do not yet list it as supported.
Rejected: django-ninja, because it moves away from the DRF stack the role asks for.
Enforced by: `backend/pyproject.toml`.

### D2. Synchronous views behind gunicorn
A plan needs one routing call and one or two batched weather calls (`weather.md`), so there is little
to overlap. Sync views keep request handling and tests simple, and gunicorn workers give concurrency
across requests.
Rejected: async DRF views with httpx, because DRF's async support is partial and the gain is one
round-trip at most.
Enforced by: `backend/Dockerfile` (gunicorn entrypoint).

### D3. Stateless: no database, Redis as a cache only
Trips are computed from the request and provider data, and nothing is stored per user. Django runs
with no database configured and without `django.contrib.auth`, sessions or admin, so there are no
migrations and nothing to back up. Redis caches provider responses; if Redis is down the app still
answers, only slower.
Rejected: an unused SQLite database, because a configured database invites state the design does not
need. Rejected: Postgres with saved trips, because it is a feature the brief does not ask for (see
`BACKLOG.md`).
Enforced by: `backend/config/settings.py` (`DATABASES = {}`, `INSTALLED_APPS`).

### D4. Python 3.14 managed by uv
uv resolves and locks dependencies quickly and reproducibly (`uv.lock`), and the Docker build
installs from the same lock with `--frozen`, so CI, the image and a laptop run identical versions.
Rejected: pip with `requirements.txt`, because it has no lock with hashes for transitive dependencies.
Enforced by: `backend/.python-version`, `backend/uv.lock`, `backend/Dockerfile`.

### D5. Configuration from environment variables only
Every setting that differs between laptop, CI and the VM comes from the environment, with safe
defaults for local development and none for secrets in production (`SECRET_KEY` must be set when
`DEBUG` is off). One `.env.example` documents every variable.
Rejected: per-environment settings modules, because they duplicate settings and hide which values
actually differ.
Enforced by: `backend/config/settings.py`, `backend/.env.example`.

### D6. Test pyramid
- pytest table tests for every band edge and load rule, and ranking tests (`risk-classification.md`,
  `recommendation.md`).
- API and adapter tests on recorded provider fixtures. Tests never touch the network.
- vitest for frontend logic: frame indexing, client-side classification, colour mapping.
- One Playwright end-to-end test: plan a trip and scrub the slider (#16).
Coverage is reported but has no target percentage. A number target rewards testing trivial code.
Rejected: backend-only tests, because half the grade is the UI.
Enforced by: `backend/pyproject.toml` (`[tool.pytest.ini_options]`), CI (#4).
