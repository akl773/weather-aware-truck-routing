# Walkthrough

An outline for the recorded walkthrough, about eight minutes, in the order of the grading areas.
Every step runs on the live site, https://spotter.akhilsingh.in.

## 1. The problem and the answer (30 s)

- A dispatcher picks between three truck routes. The forecast at the truck's ETA, not at
  departure, decides which is safest, and a heavier truck is at more risk in high wind.
- One screen: the trip form and route cards on the left, the map in the middle, the 48-hour
  timeline along the bottom.

## 2. Logic (40%) (3 min)

Plan Denver to Salt Lake City, 45,000 lb, checking every 25 miles.

- **Three routes.** Point out a Fallback chip: when the router offers fewer than three distinct
  routes, the rest come from a via point off the direct line (`routing.md` D4). The load also goes
  to the router, so a heavier truck can be sent another way (`routing.md` D2).
- **Checkpoints at the ETA.** Expand the checkpoint list: mile, ETA in the browser's zone, the
  readings interpolated to that minute, and the level with the reason
  (`checkpoints-and-eta.md`, `risk-classification.md`).
- **Bands and load rules.** Show the table in the README: four wind, rain and snow bands, No
  Travel past the top, and wind raised one band above 30,000 lb (Severe to No Travel) and above
  40,000 lb (High to Severe). Every edge is tested on both sides
  (`backend/tests/risk/test_bands.py`).
- **Unknown is not Low.** A checkpoint without a full forecast is Unknown, ranks below every
  known level except No Travel, and shows grey (`plan-api.md` D3, `recommendation.md` D7).
- **Ranking.** The cards are in ranking order: miles of No Travel, then Unknown, Severe, High, the
  mean level, then duration. The recommendation says which of those decided it
  (`recommendation.md` D3, D6, D7).
- **Every route through No Travel.** The red alert names the least-bad route and suggests a later
  departure (`recommendation.md` D5).

## 3. UI, map and heatmap (40%) (3 min)

- Click a route on the map and on a card: one selection drives both (`ui.md` D7). Hover a
  checkpoint for its tooltip; hover a row in the list to find it on the map.
- The heatmap: the corridor within 25 miles of every route, coloured by the level a checkpoint
  there would get for this load, beneath the map's labels (`corridor-heatmap.md` D1, D2, D5).
- Press Play: 48 hours in 16 seconds, the colours blending between hourly frames, each route's
  truck where its ETAs put it. Drag the slider back and forth.
- Open the network panel and scrub: no requests. Switch to Wind, Rain and Snow: continuous ramps
  with their units, never level colours (`corridor-heatmap.md` D6, D7).
- Performance: one request for all 49 frames (about 30 KB gzipped); a slider step costs about
  11 ms at p95 (measurements in `corridor-heatmap.md` D7).
- Keyboard: Tab from the form to the cards, arrows on the slider, Page Up and Page Down for three
  hours.

## 4. Code quality (15%) (1 min)

- `backend/risk/` is pure functions with no Django, I/O or clock; provider quirks stop at the
  adapters; units are imperial inside the app (`AGENTS.md`).
- Tests: table tests for every edge, API tests on recorded provider responses, frontend unit
  tests, and one Playwright test that plans, compares and scrubs. CI runs all of them and checks
  the frontend's API types against the backend's schema.

## 5. Documentation (5%) (30 s)

- `docs/decisions/`: one record per area, each decision with its reason, the alternatives
  rejected and the code and tests that enforce it.
- `docs/SPEC.md` lists the brief's gaps and how each was settled.
