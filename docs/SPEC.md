# Spec

The brief this repo implements, restated so it can be read next to the code. Where the brief is
ambiguous, the resolution lives in `docs/decisions/`, never here.

## Goal

A React + Django web app that helps a truck driver choose the safest route, weighing weather, load
weight and travel time.

## Inputs

- Origin and destination
- Departure date and time
- Load weight

## Behaviour

1. Generate **3 route options** with a routing API.
2. Sample weather every **10 / 25 / 50 miles** along each route, at the truck's **estimated arrival
   time** at each checkpoint.
3. Classify weather risk at each checkpoint with the rules below.
4. Recommend the best route, balancing weather risk and travel time.
5. Show all routes, checkpoints, risk levels, ETAs and route summaries on a map.
6. Show a **weather heatmap along the trip corridor** with a **0–48 hour forecast slider**.

Third-party APIs may be used for routing, geocoding and weather.

## Risk table

| Condition | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind | <25 mph | 25–34 | 35–44 | 45–54 | ≥55 mph |
| Rain | <0.10 in/hr | 0.10–0.25 | 0.25–0.50 | 0.50–1.00 | >1.00 |
| Snow | <0.5 in/hr | 0.5–1.0 | 1.0–2.0 | 2.0–3.0 | >3.0 |

## Load rules

- ≥55 mph → No Travel for any load
- 45–54 mph and >30,000 lb → No Travel
- 35–44 mph and >40,000 lb → Severe

## Recommendation order

Prefer, in order:

1. Fewest Severe miles
2. Fewest High miles
3. Lowest average risk
4. Shortest travel time

## Grading weights

| Weight | Area |
|---|---|
| 40% | Routes, weather, risk and recommendation logic |
| 40% | UI, map and heatmap smoothness and performance |
| 15% | Code quality |
| 5% | Documentation and walkthrough |

"Prioritize correctness and clarity over extra features."

## Known gaps in the brief

Each is settled in a decision record:

- Band ranges share their endpoints (0.25 in/hr is in both Moderate and High).
- The No Travel column uses ≥ for wind but > for rain and snow.
- The recommendation order never mentions No Travel.
- "10 / 25 / 50 miles" does not say who picks the interval.
- The risk table is per point; the ranking is in miles.
- "Average risk" has no stated weighting.
