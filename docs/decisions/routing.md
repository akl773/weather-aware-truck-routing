# Routing

Status: decided by Akhil, 2026-10-18. Issue: #7.

## North Star
Give every trip three genuinely different truck routes, each with a polyline and a driving time for
every stretch of it, so checkpoints get real ETAs. The routing provider's names, units and failure
modes stop at the adapter; the rest of the app sees miles, seconds and latitude/longitude points.
Out of scope: height, hazmat and hours-of-service limits (`BACKLOG.md`).

## Decisions

### D1. Stadia Maps' hosted Valhalla, truck costing
Valhalla's `truck` costing respects weight, height and access restrictions, returns native
alternates, and reports time and length per maneuver along a polyline6 shape. Stadia also offers
geocoding autocomplete under the same key. A 2,855-mile New York to Los Angeles request returned in
one call, so long-haul trips need no splitting.
Rejected: HERE Routing v8 truck mode, the first choice, because its free plan requires a credit card
at sign-up.
Rejected: Google Routes and Mapbox Directions, because neither has a truck profile.
Rejected: openrouteservice's HGV profile, because its alternative routes are limited to short trips
(100 km at the time of writing).
Rejected: the public OSRM demo server, because it has no truck profile and no usage terms for an app.
Enforced by: `providers.stadia.StadiaMaps`.

### D2. The truck weight sent to the provider is a 35,000 lb tractor-trailer plus the load
Valhalla's `weight` is the whole vehicle in metric tons and gates weight-restricted bridges and
roads. The spec's input is the load, so the adapter adds a typical empty tractor with a 53 ft van
trailer (35,000 lb) and converts to metric tons. A full 45,000 lb load gives 80,000 lb, the US
federal gross limit.
Rejected: sending the load alone, because a 20,000 lb load would route as a 9-ton truck and use
roads a loaded rig cannot.
Rejected: omitting the weight, because Valhalla then assumes a fixed 21.77 t for every trip and the
load input changes nothing about the route.
Enforced by: `providers.stadia.gross_weight_tonnes`; `test_gross_weight_adds_the_tractor_trailer`.

### D3. A route is a polyline with cumulative miles and seconds at every point
The adapter returns `Route(points, cum_miles, cum_s, …)`. Valhalla reports time and length per
maneuver; the adapter spreads each maneuver's time and length over its shape points in proportion to
their great-circle length, so the last point carries exactly the provider's total distance and
duration. Checkpoint ETAs (#8) then read the time at any mile without an average speed.
Rejected: one average speed for the whole route, because a route's fast interstate stretch and
slow mountain stretch would get the same pace, misplacing ETAs by hours on long trips.
Enforced by: `providers.stadia.parse_trip`; `test_cumulative_values_end_at_the_provider_totals`.

### D4. Missing routes are filled by routing through an offset via point
When the provider returns fewer than three routes, the app requests origin → via → destination,
where the via point sits at the primary route's halfway point, offset perpendicular to the
origin-destination line by 15% of the straight-line distance, first to one side, then the other,
then 30% each side. The via point is a Valhalla `through` location, so the truck passes it without
stopping. Candidates are tried in that order until three distinct routes exist or the four
candidates are used up; then the trip shows what it has.
Rejected: asking for more alternates, because Valhalla caps them and often returns one or two for
corridors with a single sensible road.
Rejected: fixed via cities, because they do not generalise to arbitrary trips.
Enforced by: `providers.routing.plan_routes`, `providers.geo.offset_point`;
`test_two_provider_routes_get_a_fallback_third`, `test_one_provider_route_gets_two_fallbacks`.

### D5. Two routes are the same option when more than 80% of one runs on the other
Both routes are resampled every 0.25 mile; a sample is on the other route when a sample of it lies
within 0.3 mile. A candidate whose overlap with any kept route exceeds 80% is dropped. Resampling
matters because Valhalla puts shape points miles apart on straight interstates, and comparing raw
points would miss shared road.
Rejected: comparing total distance and duration, because two routes can match on both and still
follow different roads.
Enforced by: `providers.geo.overlap_share`; `test_overlap_of_a_route_with_itself_is_total`,
`test_routes_sharing_more_than_80_percent_are_one_option`.

### D6. Places are picked from autocomplete; the plan receives coordinates
The browser calls `GET /api/places?q=…`, which proxies Stadia autocomplete (US, Canada, Mexico) and
returns label, latitude and longitude. The plan request carries the picked coordinates, so the
server never guesses which "Springfield" the user meant. The key stays on the server.
Rejected: free-text geocoding at plan time, because an ambiguous name silently picks one match.
Enforced by: `trips.views.PlacesView`; `test_places_returns_label_and_coordinates`.

### D7. Provider responses are cached, and the cache never takes the app down
Raw provider responses are cached in Redis, keyed by the request: routes for 6 hours, autocomplete
for 7 days. A cache read or write that fails is logged and treated as a miss, so a Redis outage
costs latency, never a failed request (stack D3).
Rejected: caching parsed `Route` objects, because a code change to parsing would then serve stale
shapes until expiry.
Enforced by: `providers.cache.fetch_cached`; `test_cache_outage_falls_through_to_the_provider`.

### D8. Tests replay recorded provider responses and fail on any unrecorded request
`tests/providers/record_fixtures.py` runs each scenario against the live API once and saves request
and response pairs, without the key. Tests replay them through an `httpx.MockTransport`; a request
with no recording fails the test, so tests can never reach the network.
Rejected: hand-written fake responses, because they encode what we think the provider returns
rather than what it does.
Enforced by: `tests/providers/replay.py`.
