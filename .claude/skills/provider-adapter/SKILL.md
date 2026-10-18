---
name: provider-adapter
description: How routing, geocoding and weather providers are wrapped in backend/providers/, and the drill for changing a provider request, adding a provider, or re-recording fixtures. Use when touching backend/providers/, tests/providers/fixtures, or when a provider returns something unexpected.
---

# Provider adapters

Decisions: `docs/decisions/routing.md` (D1–D8), and `weather.md` once it exists. Read them first.

## The boundary

| Module | Holds |
|---|---|
| `providers/geo.py` | `Point`, distances, polyline decoding, resampling, overlap, via-point offset. Pure |
| `providers/routing.py` | `Route` (points, cumulative miles and seconds), `Router` protocol, `plan_routes` |
| `providers/stadia.py` | Valhalla request/response, weight conversion, error mapping, `default()` client |
| `providers/cache.py` | `fetch_cached`: raw responses in Redis, fail-open |
| `providers/errors.py` | `ProviderError` (502) and `NoRouteError` (422), mapped in `trips/errors.py` |

Provider field names, units and error codes never leave the adapter module. If a view or `risk/`
needs a provider field, add it to `Route` (or the weather equivalent) in app units.

## Changing a request

1. Edit the adapter. Bump the cache namespace (`stadia:route:v1` → `v2`) when the response shape
   or meaning changes, so old cached responses are not parsed by new code.
2. Re-record: `cd backend && STADIA_API_KEY=... uv run python -m tests.providers.record_fixtures`.
   The key lives in `~/.config/spotter/stadia.env` on the maintainer's machine, never in the repo.
3. Read the recorder's summary line per scenario (request count, size). A changed request count
   means fallback behaviour changed; check the tests say why.
4. `uv run pytest tests/providers` and commit fixtures together with the code that needs them.

## Adding a provider

1. A decision in `docs/decisions/` naming what it replaces or adds and the rejected options.
2. A module exposing app types only, raising `ProviderError` / `NoRouteError`.
3. Cache through `fetch_cached` with a versioned namespace and a TTL that matches how fast the data
   changes.
4. Scenarios in `tests/providers/scenarios.py`, recordings via the recorder, replay tests.

## Traps

- Keys travel in query strings. `config/settings.py` keeps the `httpx` logger at WARNING; never
  log a request URL yourself, and never put a key into a cache key (`request_key` hashes the body
  and params you pass, so pass them without the key).
- Tests must not reach the network. A request with no recording raises `AssertionError` naming the
  path; re-record instead of hand-editing JSON.
- `tests/providers/conftest.py` clears the cache around every test, so a cached response can never
  hide a missing recording.
- Valhalla returns at most two alternates and often fewer; `plan_routes` fills the rest. Never
  assume three routes in code that consumes `plan_routes`.
