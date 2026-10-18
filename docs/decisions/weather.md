# Weather

Status: decided by Akhil, 2026-10-18. Issue: #9.

## North Star
Hourly wind, gusts, rain and snow in the spec's units for any point on a North American route, up to
the forecast horizon, fast enough for a cross-country plan and cheap enough to stay inside a free
tier. A value the provider does not have is unknown, never zero.
Out of scope: ice, visibility, temperature and official alerts (`BACKLOG.md`).

## Decisions

### D1. Open-Meteo's forecast API, best-match model
No key, hourly data to about 15 days, and many locations in one request. Its best-match model uses
NOAA's 3 km HRRR over the US for the first two days and global models after, which is the
resolution a corridor heatmap needs.
Rejected: the National Weather Service API, because it is US-only and needs two calls per point
with no batching.
Rejected: OpenWeather and Tomorrow.io, because hourly forecasts beyond two days or batched
locations sit on paid plans.
Enforced by: `providers.open_meteo.OpenMeteo`.

### D2. Rain is rain plus showers; snow is snowfall depth
The adapter requests `wind_speed_10m`, `wind_gusts_10m`, `rain`, `showers` and `snowfall` in mph
and inches. Rain in/hr is `rain + showers`, the liquid falling in the hour from both large-scale
and convective systems. Snow in/hr is `snowfall`, inches of fresh snow, which is what the spec's
0.5 to 3.0 in/hr bands describe.
Rejected: `precipitation`, because it adds snow's water equivalent to rain and would count a
snowstorm twice.
Enforced by: `providers.open_meteo.parse_location`; `test_rain_adds_showers`.

### D3. Hourly totals are valid at the middle of their hour
Open-Meteo's rain, showers, snowfall and gusts at hour T are the sum or maximum over the hour
ending at T. The adapter places them at T − 30 min; wind speed is an instant reading at T.
Interpolation at an ETA (checkpoints-and-eta D4) then uses the right time for each.
Rejected: placing totals at T, because every storm would arrive 30 minutes late on the map.
Enforced by: `providers.open_meteo.Series.period_times`; `test_hourly_totals_sit_mid_hour`.

### D4. Points snap to a 0.05° lattice and are fetched in batches of 100
Open-Meteo counts each location as one call (free tier: 600 a minute, 5,000 an hour, 10,000 a
day). Snapping to 0.05° (about 5 km, close to HRRR's 3 km grid) lets nearby
checkpoints on overlapping routes, and the corridor heatmap, share one location. Batches of 100
keep each request under a few seconds.
Rejected: one request per point, because a 350-checkpoint plan would take minutes.
Rejected: a coarser 0.25° lattice, because it averages away the HRRR detail.
Enforced by: `providers.open_meteo.snap`, `BATCH_SIZE`; `test_nearby_points_share_one_location`,
`test_large_requests_are_batched`.

### D5. Every fetch covers a whole-day window from the hour before departure
The window starts one hour before departure and spans at least 50 hours, rounded up to whole days,
so the plan (departure to last ETA) and the 48-hour heatmap request the same window and share the
cache. The end is clamped to the provider's range (today plus 15 days); hours past it come back
unknown.
Rejected: a window fitted to each request, because the plan and the heatmap would never share a
cached response.
Enforced by: `providers.open_meteo.fetch_window`; `test_window_is_shared_by_plan_and_heatmap`,
`test_window_is_clamped_to_the_provider_range`.

### D6. Each lattice point's window is cached for an hour, fail-open
Cached per lattice point and window, so a second plan along the same corridor makes no weather
call. One hour matches how often the underlying models refresh. Cache failures fall through to the
provider (routing D7).
Rejected: caching whole requests, because two plans rarely ask for exactly the same set of points.
Enforced by: `providers.cache.fetch_many_cached`; `test_a_second_identical_fetch_makes_no_call`.
