# backend/AGENTS.md

Backend rules on top of the root `AGENTS.md`.

## Invariants

- **`risk/` is pure.** No Django, no I/O, no clock. `tests/risk/test_purity.py` enforces the import
  allowlist. Recipes for changing rules: `.claude/skills/risk-rules/`.
- **Units are the spec's:** mph, in/hr, lb, miles. Field names carry the unit (`wind_mph`,
  `rain_in_hr`, `load_lb`). Converting from a provider's units happens only in its adapter.
- **Levels are `risk.levels.Level`,** an ordered `IntEnum`. Compare with `is` or `>`, never by label
  string.
- **Numbers shown to the user are rounded once, here,** with `risk.scoring.display_round` (half up;
  No Travel miles round up). The API sends rounded values; the frontend only pads them to fixed
  decimals and never rounds a raw value itself.
- **No reading is ever defaulted to zero.** Missing or impossible values raise or are marked
  unknown, because zero means "calm" and reads as Low.

## Layout

| Path | Holds |
|---|---|
| `config/` | settings, URLs, health endpoint |
| `risk/` | classification, load rules, ranking (pure) |
| `tests/` | pytest; mirrors the package layout |

## Commands

`uv run pytest`, `uv run ruff check .`, `uv run ruff format .`, or `make test` / `make check` from
the root.
