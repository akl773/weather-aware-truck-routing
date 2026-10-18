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
- vitest for frontend logic: trip validation, route segments, frame blending, colour mapping and
  truck positions. The browser never classifies risk (corridor-heatmap D2).
- One Playwright end-to-end test in Chromium: plan a trip, compare the three routes and scrub the
  slider, checking that scrubbing makes no request (#16). The browser's API calls are answered from
  responses recorded off our own API, and the basemap is a blank style, so the test needs no keys,
  fetches no tiles and runs the same in CI as on a laptop. The backend's own tests cover how those
  answers are made.
Coverage is reported but has no target percentage. A number target rewards testing trivial code.
Rejected: backend-only tests, because half the grade is the UI.
Enforced by: `backend/pyproject.toml` (`[tool.pytest.ini_options]`), CI (#4),
`frontend/e2e/plan-and-scrub.spec.ts`.

## Frontend

### D7. Vite + React + strict TypeScript, built to static files
The app is one interactive map page, so it gains nothing from server rendering. Vite builds static
assets that nginx serves next to the API, on one origin (`deployment.md`).
TypeScript is pinned to 5.9.
Rejected: Next.js, because SSR and routing add a server process with nothing to render.
Rejected: TypeScript 7, because typescript-eslint (`<6.1`) and openapi-typescript (`^5`) do not
support it yet.
Enforced by: `frontend/package.json`, `frontend/tsconfig.json` (`strict`).

### D8. MUI for controls
The form, route cards, slider and toggles are standard controls with accessibility handled. The role
asks for React with Material UI.
Rejected: hand-built controls, because accessible sliders and autocompletes are slow to get right.
Enforced by: `frontend/src/theme.ts`.

### D9. MapLibre GL + deck.gl in interleaved mode
deck.gl draws routes, checkpoints and corridor cells on the GPU. Moving the slider only changes one
layer's colour attribute, which keeps scrubbing smooth (`corridor-heatmap.md`). `MapLibreOverlay`
with `interleaved` renders deck.gl layers inside MapLibre's own render pass, so the corridor can sit
beneath road names and place labels.
Rejected: Mapbox GL JS, because it needs an access token and is proprietary from v2.
Rejected: Leaflet, because DOM and canvas redraws stutter at grid sizes we need.
Enforced by: `frontend/src/map/DeckOverlay.tsx`.

### D10. OpenFreeMap Positron basemap
Free, no API key, no usage cap, MapLibre vector style. Positron is near-greyscale, so the five risk
colours stay the most saturated thing on the map.
Rejected: MapTiler, because its key would ship in client code and the free tier is capped.
Rejected: OpenFreeMap Liberty, because its colourful roads and parks compete with the risk colours.
Enforced by: `frontend/src/map/basemap.ts`.

### D11. TanStack Query for server state, React state for the rest
Plan and corridor responses are server state: cached per trip, deduplicated, with loading and error
states. Slider hour, selected route and the variable toggle are UI state held in React.
Rejected: Redux Toolkit or Zustand, because no state is shared widely enough to need a store yet.
Enforced by: `frontend/src/main.tsx` (`QueryClientProvider`).

### D12. API types generated from the OpenAPI schema
`npm run api:types` runs openapi-typescript against `/api/schema/`, and openapi-fetch calls the API
with those types. A renamed field on the backend becomes a type error on the frontend.
Rejected: hand-written TypeScript types, because they drift from the serializers.
Enforced by: `frontend/src/api/client.ts`, `frontend/src/api/schema.d.ts`.
