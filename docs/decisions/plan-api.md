# Plan API

Status: decided by Akhil, 2026-10-18. Issue: #10.

## North Star
One request turns a trip into everything the map and the route cards show: three routes, their
checkpoints with ETA, readings, level and driver condition, each route's summary and the
recommendation with its reason. Every number in the response is the number the UI prints, so the
screen and ranking agree; weather classification uses forecast precision before display rounding.

## Decisions

### D1. `POST /api/plan` takes picked places, a timezone-aware departure, load and interval
`origin` and `destination` are places from `/api/places` (label, latitude, longitude; routing D6).
`departure` is ISO 8601 with an offset, from one hour ago to seven days ahead: seven days plus the
longest trip stays inside the weather range (weather D5). `load_lb` is 0 to 80,000. `interval_mi`
is 10, 25 or 50 and defaults to 25. Origin and destination must be at least one mile apart.
Rejected: accepting a naive departure and assuming a zone, because the server cannot know the
driver's clock.
Enforced by: `trips.serializers.PlanRequestSerializer`; `test_plan_rejects_*`.

### D2. Classify forecast readings before rounding them for display
Updated for #33: interpolated readings retain their precision through checkpoint and corridor
classification, including load rules, gust flags, drivers and route summaries. The risk engine's
six-decimal float-noise normalization still applies (risk-classification D7).
Only response serialization rounds wind and gusts to 0.1 mph and rain and snow to 0.01 in/hr,
half up (recommendation D4). The UI explains that readings are rounded and risk uses the unrounded
forecast. Thus rain at 1.004 in/hr is No Travel even though its displayed reading is 1.00.
This replaces the earlier decision to classify display-rounded readings: that changed the spec's
thresholds, hiding No Travel precipitation and prematurely escalating wind/load bands.
Rejected: adding a fixed number of display decimals, because any fixed precision can hide an edge.
Enforced by: `trips.plan.readings_at`, `trips.serializers`;
`test_classification_uses_forecast_precision_before_display_rounding`.

### D3. A checkpoint without a full forecast has an unknown level, unless it is already No Travel
If wind, rain or snow is unknown at the ETA (checkpoints-and-eta D5), the checkpoint's level is
unknown. The missing readings are sent as `null` and the known ones as usual. One exception: when a
known reading is No Travel on its own, the level is No Travel, because the level is the worst
condition (risk-classification D5) and nothing missing could lower it. Without that, a route with
60 mph wind and no rain forecast would rank as unknown, after No Travel, and could be recommended
over the same wind with a dry forecast. A missing gust alone only clears the gust flag, because
gusts never set the level (risk-classification D3). Unknown miles are ranked in recommendation D7.
Rejected: classifying the readings that are known, because a checkpoint with no rain forecast would
read as dry.
Enforced by: `trips.plan.classify_checkpoint`; `test_missing_rain_makes_the_level_unknown`,
`test_a_known_no_travel_reading_decides_a_partial_forecast`,
`test_a_partial_forecast_below_no_travel_is_unknown`, `test_missing_gust_only_clears_the_gust_flag`.

### D4. Route geometry is simplified and carries the mile of every point
Each route's path is simplified (Douglas-Peucker, 0.0005°, about 50 m) and sent as
`[longitude, latitude, mile]` triples. The mile lets the map colour each checkpoint's owned stretch
and place the truck marker at any hour without recomputing distances in the browser.
Rejected: the full provider shape, because a cross-country route has 40,000 points.
Rejected: an encoded polyline, because the browser would decode it and then recompute the miles the
server already has.
Enforced by: `providers.geo.simplify`, `trips.plan`; `test_simplified_path_keeps_the_ends_and_miles`.

### D5. Failures keep one error shape
Invalid input is 400, no truck route is 422, a provider failure is 502; every body is
`{"detail": …}`, with `fields` added for invalid input. A body over Django's 2.5 MB limit and a
well-formed but impossible date are invalid input too, never a 500 or an HTML page.
Enforced by: `trips.errors.exception_handler`; `test_plan_*_error`,
`test_an_oversized_body_keeps_the_error_shape`, `test_plan_rejects_a_departure_that_is_not_a_date`.
