---
name: risk-rules
description: How the spec's risk table, load rules and checkpoint level are encoded in backend/risk/, and the exact drill for changing a threshold or adding a rule without breaking a decided edge. Use when touching backend/risk/classification.py, its tests, or docs/decisions/risk-classification.md, or when asked "why is this checkpoint Severe".
---

# Risk rules

The graded logic. Everything lives in `backend/risk/classification.py` and is decided in
`docs/decisions/risk-classification.md` (D1–D6). Read that file first; do not re-decide anything in
it.

## Where each rule lives

| Rule | Code | Decision |
|---|---|---|
| Band edges per condition | `WIND_MPH`, `RAIN_IN_HR`, `SNOW_IN_HR` (`BandEdges`) | D1, D2 |
| Load rules | `LOAD_RULES` (`LoadRule`), applied in `wind_band_for_load` | D4 |
| Checkpoint level, drivers | `classify` | D5 |
| Gust flag | `classify` (`gusty`) | D3 |
| Input validation | `Conditions.__post_init__`, `_require_reading` | D6 |
| Float-noise snapping | `snap`, used by `BandEdges.band` and the load rules | D7 |

## Changing a threshold or rule

1. Edit the decision record first: the table at the top and the decision that owns the rule. A rule
   change without a record change is a bug by definition (AGENTS.md).
2. Add test rows for both sides of the new edge (`*_CASES` tables in
   `backend/tests/risk/test_bands.py`). Run them and watch them fail.
3. Change only the data: the `BandEdges` floors and No Travel operator, or a `LoadRule`. The
   functions are generic over these tables, so a threshold change needs no logic change.
4. `make test`, then check the monotonicity test still passes: a higher value must never give a
   lower band.

## Traps

- **The No Travel edge is not half-open for rain and snow.** Exactly 1.00 in/hr rain and 3.0 in/hr
  snow are Severe (D2). Wind at exactly 55 mph is No Travel. Do not "simplify" to one operator.
- **"More than 30,000 lb" is strict.** A load of exactly 30,000 lb is unaffected (D4).
- **Gusts never change the level**, only `gusty` (D3). Ranking reads `level`.
- **Compare through `snap`.** Any new comparison against an edge must snap the reading first, or
  54.99999999999999 mph escapes the No Travel rule (D7).
- **Never default a missing reading to 0.** `Conditions` rejects negatives and NaN. Unknown weather
  (past the forecast horizon) is handled before classification, in the weather layer.
- `backend/tests/risk/test_purity.py` fails the build if `risk/` imports anything outside a small
  standard-library allowlist. Keep it pure; pass values in as arguments.

## Scoring and ranking

Decided in `docs/decisions/recommendation.md` (D1–D6).

| Rule | Code | Decision |
|---|---|---|
| Owned miles (centred stretches, sum to route length) | `risk.scoring.owned_miles` | D1 |
| Miles at level, owned-mile-weighted mean level | `risk.scoring.summarize_route` | D2 |
| Ranking order, No Travel first | `risk.recommendation.ranking_key` | D3 |
| Compare at display precision, half up | `risk.scoring.display_round` | D4 |
| All routes cross No Travel | `Recommendation.all_routes_cross_no_travel` | D5 |
| Reason text | `risk.recommendation._explain` | D6 |

Traps:

- **Never compare raw miles or mean level.** Go through `ranking_key`; a 0.0001 mi difference must
  not decide the recommendation.
- **Never round again in the UI.** The API sends `display_round` values; Python's `round` and
  JavaScript's `toFixed` disagree on halves.
- **Ties keep the provider's order** because `sorted` is stable. Do not add a tie-breaker that is not
  in the decision record.
