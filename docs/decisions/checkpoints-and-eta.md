# Checkpoints and ETA

Status: decided by Akhil, 2026-10-18. Issue: #8.

## North Star
Read the weather where the truck will be, when it will be there. Every checkpoint gets a position on
the route, a time of arrival from the provider's driving times, and conditions interpolated to that
minute, so a storm crossing the route at 14:00 is seen by the checkpoint the truck reaches at 14:00
and not by one it passes at noon.
Out of scope: rest breaks and hours-of-service limits (`BACKLOG.md`).

## Decisions

### D1. Checkpoints sit at the origin, every interval after it, and the destination
Mile 0 is a checkpoint because the truck is exposed to the weather it leaves in. Then one every
interval, and the destination. If the destination is within 0.05 mile of the last interval
multiple, that multiple becomes the destination, so checkpoints stay strictly increasing
(recommendation D1) without a near-duplicate pair.
Rejected: starting at the first interval, because the origin's weather would be ignored and a trip
shorter than one interval would have a single checkpoint at the destination.
Enforced by: `trips.checkpoints.checkpoint_miles`; `test_checkpoints_on_an_exact_multiple`,
`test_short_final_segment_ends_at_the_destination`, `test_trip_shorter_than_one_interval`.

### D2. The driver picks 10, 25 or 50 miles; 25 is the default
The spec lists three intervals without saying who chooses. The form offers all three. 25 miles
resolves a typical storm cell (tens of miles across) and keeps a cross-country plan near 350
checkpoints across three routes, inside the weather provider's per-minute limit (weather D4).
Rejected: a fixed interval, because the spec names three.
Enforced by: `trips.checkpoints.INTERVALS_MI`, the plan request serializer (#10).

### D3. ETA is departure plus the provider's driving time to the checkpoint's mile
The route carries cumulative seconds at every shape point (routing D3); the time at a checkpoint is
interpolated linearly between the shape points around its mile. Times are timezone-aware UTC.
Rejected: distance divided by an average speed, because it ignores where the route is slow.
Rejected: adding rest stops, because hours-of-service rules are out of scope; the ETA is the
earliest the truck can arrive.
Enforced by: `trips.checkpoints.seconds_at_mile`, `place_checkpoints`;
`test_eta_follows_the_route_pace_not_an_average`.

### D4. Conditions at the ETA are interpolated linearly between the forecast samples around it
Each condition is interpolated on its own between the two samples bracketing the ETA. The weather
adapter states when each sample is valid (weather.md); this step takes those times as given.
Rejected: the nearest forecast hour, because conditions would jump at the half hour and a checkpoint
at 14:29 would read 14:00 weather.
Enforced by: `trips.checkpoints.value_at`; `test_value_halfway_between_samples`.

### D5. An ETA outside the forecast, or a missing sample, gives an unknown value
`value_at` returns `None` when the ETA is before the first sample, after the last, or either
bracketing sample is missing. It never returns 0, because 0 reads as calm.
Rejected: holding the last known value, because a forecast that ends before the truck arrives says
nothing about that arrival.
Enforced by: `trips.checkpoints.value_at`; `test_value_outside_the_forecast_is_unknown`,
`test_missing_sample_is_unknown`.
