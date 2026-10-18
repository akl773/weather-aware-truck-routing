# AGENTS.md

Rules for anyone changing this repo, human or agent. `CLAUDE.md` points here so every tool reads the
same file.

## What this is

A web app that ranks three truck routes by forecast weather at the truck's ETA, adjusted for load
weight, and shows the trip corridor's weather for the next 48 hours. Django + DRF backend, React +
TypeScript frontend, MapLibre + deck.gl map.

## Read before coding

1. `docs/SPEC.md`: the brief, and the gaps in it.
2. `docs/CONTEXT.md`: the vocabulary. Use these terms in code, API fields and UI copy.
3. `docs/decisions/`: settled choices. Do not re-decide them; change one only through a PR that
   edits the record.
4. `docs/ISSUE_WORKFLOW.md`: how an issue becomes a merged PR.
5. `docs/BACKLOG.md`: ideas that are deliberately not built. Do not build them unless asked.

## Layout

- `backend/`: Django project. Backend invariants: `backend/AGENTS.md`.
  - `risk/`: classification, load rules and ranking. Pure functions.
  - `providers/`: routing, geocoding and weather adapters.
  - `trips/`: API views and serializers that compose the two.
- `frontend/`: Vite + React app.
- `docs/`: spec, context, decisions, workflow, backlog.
- `.claude/skills/`: task recipes for agents (changing a risk rule, adding a provider, deploying).

## Commands

Run from the repo root. `make help` lists every target.

| Command | What it does |
|---|---|
| `make dev` | api on :8000, web on :5173 (proxies `/api`), redis; all reload on save |
| `make check` | ruff lint + format check, eslint, `tsc`. The pre-push hook runs this |
| `make test` | pytest and vitest |
| `make sanity` | everything CI runs: check, test and the production web build |
| `make api-types` | regenerate `frontend/src/api/schema.d.ts` after any serializer change |
| `make hooks-install` | gitleaks on commit, `make check` on push |
| `make deploy` / `make prod-check` | ship HEAD (must be on `origin/main`) to production / compare the live SHA with `origin/main`; see `.claude/skills/deploy/` |

CI runs the same gates and also fails when `schema.d.ts` is out of date with the backend schema.

## Architecture rules

- `risk/` imports nothing from Django, does no I/O, and reads no clock. Everything it needs comes in
  as arguments. This keeps the graded logic testable with plain tables.
- Providers sit behind adapters. Provider field names, units and quirks stop at the adapter boundary.
- Units are imperial everywhere inside the app (miles, mph, in/hr, lb), because the spec is. Unit
  conversion happens only inside adapters.
- Times are timezone-aware UTC inside the app and become local time only at display.
- API keys stay on the server. The browser calls our API, never a keyed provider.

## Testing rules

- Every threshold is tested on both sides of its edge.
- Tests never call the network. Provider tests replay recorded fixtures.
- A bug fix starts with a test that fails without the fix.
- Test names state the rule: `test_rain_at_exactly_0_25_is_high`, not `test_rain_3`.

## Performance budget

- Moving the forecast slider makes no network requests.
- A slider step updates the map within one frame (16 ms) on a mid-range laptop.
- Measured numbers go into the relevant decision record, with how they were measured.

## Code style

- Comments say why, not what. Code implementing a decision cites it: `# risk-classification D2`.
- Prefer a plain function over a class until state forces otherwise.
- No dead code, commented-out code or speculative options.

## Git

- One issue, one branch, one PR. Branches: `<type>/<n>-<slug>`.
- Conventional commits with scope and issue: `feat(risk): classify snow bands (#5)`. One concern per
  commit, committed when it is green.
- PRs close their issue with `Fixes #<n>` and merge with a merge commit.
- Never commit `.env` files, keys or provider responses that contain keys.
