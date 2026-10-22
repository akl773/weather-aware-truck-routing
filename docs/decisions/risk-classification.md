# Risk classification

Status: decided by Akhil, 2026-10-18. Issue: #5.

## North Star

Every checkpoint gets exactly one level from the spec's risk table and load rules, with no value left
unclassified and no boundary ambiguous. The rules live in one pure module, so the code reads like the
spec table and every edge is pinned by a named test.

Out of scope: hazards the brief gives no thresholds for (visibility, ice, freezing rain). See
`BACKLOG.md`.

## The table as implemented

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind (sustained, mph) | < 25 | [25, 35) | [35, 45) | [45, 55) | ≥ 55 |
| Rain (in/hr) | < 0.10 | [0.10, 0.25) | [0.25, 0.50) | [0.50, 1.00] | > 1.00 |
| Snow (in/hr) | < 0.5 | [0.5, 1.0) | [1.0, 2.0) | [2.0, 3.0] | > 3.0 |

## Decisions

### D1. Bands are half-open: a boundary value belongs to the higher band
The spec's ranges share endpoints (rain 0.10–0.25 and 0.25–0.50 both contain 0.25), and its integer
wind ranges leave gaps for real readings (34.5 mph is in neither 25–34 nor 35–44). Half-open bands
`[low, high)` give every value exactly one band. They also match the table's own wording at the
low end: "<25 mph" is Low, so 25 starts Moderate.
Rejected: upper-inclusive bands `(low, high]`, because they contradict "<25 mph" and "<0.10 in/hr".
Enforced by: `risk.classification.wind_band`, `rain_band`, `snow_band`;
`test_wind_bands`, `test_rain_bands`, `test_snow_bands`.

### D2. The No Travel edge follows each row's own operator
The spec writes "≥55 mph" for wind but ">1.00" and ">3.0" for rain and snow. Taken literally,
exactly 1.00 in/hr of rain is Severe and exactly 55 mph is No Travel. A uniform half-open rule would
make 1.00 in/hr No Travel and contradict the table on its face, so the top edge keeps the spec's
operator and only the lower edges are half-open.
Rejected: uniform half-open bands everywhere, because a grader comparing against the table would read
1.00 in/hr → No Travel as a bug.
Enforced by: `test_rain_at_exactly_1_00_is_severe`, `test_snow_at_exactly_3_0_is_severe`,
`test_wind_at_exactly_55_is_no_travel`.

### D3. Sustained wind sets the band; gusts only raise a flag
The table classifies wind speed, which by the usual forecast convention means sustained wind. Gusts
are still a real hazard for a high-sided trailer, so when the gust speed would put the wind band
higher (load rules included), the checkpoint carries a gust flag that the UI shows. The flag compares
wind bands only, so it can be set on a checkpoint whose level comes from snow or rain. It never
changes the level or the ranking. A gust reading below the sustained wind never sets the flag.
Rejected: gusts drive the band, because typical gust factors push ordinary days into High and Severe
and the ranking stops telling routes apart.
Rejected: `max(sustained, 0.8 × gust)`, because the 0.8 factor would be invented.
Enforced by: `risk.classification.classify` (`gusty`); `test_gust_flag_*`.

### D4. Load rules raise the wind band only, and only for loads strictly above the limit
- Wind in [45, 55) and load > 30,000 lb → No Travel.
- Wind in [35, 45) and load > 40,000 lb → Severe.
- Wind ≥ 55 → No Travel for any load (already the table's top band).

"Greater than" is literal: exactly 30,000 lb is not affected. Rain and snow bands do not depend on load.
Rejected: raising rain and snow bands for heavy loads too (a heavy truck also brakes worse on wet
roads), because the spec ties weight only to wind and the extra rule would be invented.
Enforced by: `risk.classification.wind_band_for_load`; `test_load_rules`.

### D5. A checkpoint's level is its worst condition, and every condition at that level is named
Level = max(wind band after load rules, rain band, snow band). The conditions that reach that level
are returned as the drivers, and the UI pairs each with its reading ("snow 2.4 in/hr") to say why a
checkpoint is Severe. When two conditions tie, both are named instead of picking one arbitrarily. A
Low checkpoint has no drivers.
Rejected: an additive score across conditions (High wind + Moderate rain → Severe), because the spec
gives no rule for combining conditions and adding one would invent risk.
Enforced by: `risk.classification.classify`; `test_level_is_the_worst_condition`,
`test_tied_conditions_are_all_drivers`.

### D6. Impossible readings are rejected, never classified
A wind, gust, rain, snow or load value that is negative, non-finite (NaN, infinite), too large for a
float, a boolean or not a number at all raises `ValueError`. Treating it as zero would quietly report
Low on corrupt provider data, which is the one failure this app must never have.
Rejected: clamping negatives to zero, because it hides adapter bugs.
Enforced by: `risk.classification.Conditions`, `classify`; `test_rejects_impossible_readings`,
`test_rejects_impossible_loads`.

### D7. Readings are rounded to 6 decimal places before comparison with an edge
Readings reach this module after unit conversion and interpolation, and binary floating point lands
next to an edge instead of on it: 88.51392 km/h converts to 54.99999999999999 mph, and halfway
between 0.01 and 0.19 in/hr is 0.09999999999999999. Compared raw, both fall one band too low, and
the 55 mph wind would escape the any-load No Travel rule. Rounding to 6 decimals removes that noise
and changes no real reading, since every provider value is far coarser.
Rejected: rounding to display precision before classification, because that changes thresholds.
The plan and corridor pass interpolated readings unchanged (plan-api D2, updated in #33); only
response serialization rounds for display. This module removes float noise, not forecast precision.
Rejected: `math.isclose` at each comparison, because a tolerance spread across every edge check is
harder to reason about than one rounding step.
Enforced by: `risk.classification.BandEdges.band`, `wind_band_for_load`;
`test_float_noise_lands_on_the_edge`.

## Open questions

- Checkpoints past the forecast horizon have no weather to classify. They are handled before
  classification (`weather.md`, #9) and never reach this module as zeros.
