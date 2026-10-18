# Corridor heatmap

Status: decided by Akhil, 2026-10-18. Issues: #11 (data), #14 (rendering).

## North Star
The driver sees how the weather moves across the whole trip corridor over the next 48 hours, and
scrubbing through those hours is instant: one request fetches every frame, and the slider never
touches the network. Each cell's colour is the same risk level a checkpoint there would get, from
the same rules, so the heatmap and the route cards never disagree.
Out of scope: weather outside the corridor, forecast hours past 48, and animated radar.

## Decisions

### D1. The corridor is the grid cells within 25 miles of any route, at the finest size that fits 250 cells
Cells are squares on a global grid whose centres are multiples of the cell size in degrees. Sizes
come from a fixed ladder, 0.15° (about 15 km, the size `CONTEXT.md` aims for) up to 1.0°, and the
corridor uses the finest one with at most 250 cells. A cell belongs to the corridor if its centre
is within 25 miles (40 km) of a route, or within half its diagonal plus a mile when that is larger,
so every cell a route crosses is included. Routes are densified to a point every 2 miles before the
test (the extra mile covers the gap between those points), because a simplified path can leave tens
of miles between points on a straight interstate. Centres past a pole are never made, and
longitudes wrap into [-180, 180), the range the weather provider takes.
Each cell is one weather location (weather D4), and the free tier allows 600 a minute and 5,000 an
hour. A 15 km grid needs 758 cells for Denver to Salt Lake City and about 3,800 for New York to Los
Angeles, which is more than a minute's budget for a single trip. Capped at 250, a cross-country plan
at the default interval (about 330 locations) plus its heatmap stays under 600 a minute; measuring
three heatmaps back to back (615 locations inside a minute) did hit the limit. Measured on live
routes (three per trip) on 2026-10-18, finest size within the cap and the time to find it:

| Trip | Size | Cells | Time |
|---|---|---|---|
| Denver to Salt Lake City | 0.30° | 193 | 6 ms |
| Chicago to Denver | 0.40° | 219 | 10 ms |
| Seattle to Miami | 0.70° | 246 | 24 ms |
| New York to Los Angeles | 0.80° | 211 | 26 ms |

Centres that are multiples of 0.05° sit on the weather lattice (weather D4), so every trip through
the same region asks for the same locations and shares the cache.
Rejected: a fixed 15 km grid, because a medium trip alone would exceed the per-minute limit.
Rejected: one weather location per several cells, interpolated, because it invents detail the
forecast does not have and the cells would no longer match a checkpoint's reading.
A route set too large even at 1.0° is refused as invalid input.
Enforced by: `trips.corridor.corridor_cells`; `test_cells_cover_every_route_point`,
`test_cells_near_the_180th_meridian_wrap_into_range`, `test_no_cell_lies_past_a_pole`,
`test_a_cell_centre_24_9_miles_from_a_route_is_in_the_corridor`,
`test_a_cell_centre_25_1_miles_from_a_route_is_not`, `test_cell_size_grows_until_the_corridor_fits`,
`test_cell_centres_sit_on_the_weather_lattice`,
`test_corridor_rejects_routes_that_cover_too_much_ground`.

### D2. 49 hourly frames, hour 0 at departure, classified on the server for the trip's load
Frame k holds every cell's readings at departure + k hours, for k from 0 to 48, so the slider's two
ends are both real frames. Readings are interpolated at that instant and rounded as shown, then
classified, exactly as a checkpoint's are (checkpoints-and-eta D4, plan-api D2 and D3), so a cell's
level is the level a checkpoint there would get at that hour.
Rejected: sending raw values and classifying in the browser, because the graded rules would then
exist twice, in two languages, and a load change already needs a new plan: load is a routing input
(routing D2).
Enforced by: `trips.corridor.corridor_frames`; `test_a_cell_matches_a_plan_checkpoint_at_its_centre`,
`test_cell_readings_follow_the_checkpoint_rules`, `test_frames_run_from_departure_to_48_hours`,
`test_frame_levels_apply_the_load_rules`, `test_a_cell_without_a_full_forecast_is_unknown`.

### D3. `POST /api/corridor` takes the plan's paths, departure and load, and keeps no state
The browser already holds the plan's simplified paths (plan-api D4), so it sends them back with the
departure and load. The departure has the same bounds as a plan's (plan-api D1). Up to three paths
are accepted, each of up to 10,000 points (a simplified Seattle to Miami route has about 2,900) and
up to 8,000 miles (Key West to Prudhoe Bay is about 5,800). The length cap bounds the work, which
grows with the miles to densify: the worst input it allows, three 8,000-mile zigzags, takes 0.3 s,
where an unbounded path could take minutes and gigabytes. A path that jumps across the 180th
meridian is refused, because no route here does and it would be drawn the long way round. The
weather window is the one a plan for the same departure would fetch when its last ETA is within the
48 hours (weather D5), so most heatmaps reuse locations the plan's neighbours already cached.
Rejected: storing each plan under an id for the heatmap to reference, because it adds storage and
an expiry to a service that has none, to save an upload of 50 KB for a medium trip and about
350 KB coast to coast.
Rejected: returning the frames inside the plan response, because the routes and cards would then
wait for 250 more weather locations before showing anything.
Enforced by: `trips.serializers.CorridorRequestSerializer`, `PathField`; `test_corridor_rejects_*`,
`test_corridor_accepts_*`.

### D4. One response, frame by frame, numbers as shown
The response is the cell size, the cell centres as `[longitude, latitude]`, the start time, and one
entry per frame holding a level and the four readings for every cell, in cell order. Unknown is
`null`. Every number is rounded as the UI prints it (plan-api D2), which also keeps the JSON small.
Measured on 2026-10-18 with live Open-Meteo data, the response rendered by DRF and gzipped at
nginx's default level 6 (`gzip on` in `frontend/nginx.conf`):

| Trip | Cells | JSON | Gzipped | Uncached | Cached |
|---|---|---|---|---|---|
| Denver to Salt Lake City | 193 | 177 KB | 28 KB | 1.3 s | 0.2 s |
| New York to Los Angeles | 211 | 195 KB | 31 KB | 1.0 s | 0.3 s |

"Uncached" is two or three Open-Meteo batches; "cached" is the cache read plus computing the 49
frames. Computing the frames alone takes 114 ms for 211 cells on an Apple-silicon laptop, after
`Series.period_times` became a cached property (it was 437 ms, most of it rebuilding that tuple
for every reading).
Rejected: a binary or base64 typed-array payload, because at about 30 KB gzipped the JSON is
already small, and the browser would need a decoder and a schema of its own.
Enforced by: `trips.serializers.corridor_response`; `test_corridor_returns_a_level_per_cell_per_frame`,
`test_corridor_numbers_are_the_numbers_shown`.

### D5. The heatmap is fetched once after the plan and drawn under the routes
The browser asks for the corridor as soon as a plan arrives, with that plan's paths, departure and
load, and caches it per plan like the plan itself (ui D5): never retried on its own and never
refetched on focus or reconnect. The routes and cards show at once and the heatmap fades in when it
lands; if it fails, the timeline says so and offers a retry while the routes stay usable. Cells are
drawn as squares one cell size wide, under the routes and checkpoints, translucent enough that the
basemap's towns and roads stay readable.
Rejected: fetching the corridor in parallel with the plan, because its input is the plan's paths.
Enforced by: `frontend/src/corridor/useCorridor.ts`, `frontend/src/corridor/heatmapLayers.ts`.

### D6. Risk is the default view; wind, rain and snow are continuous ramps, not levels
The default view colours each cell by its level for the trip's load, in the same colours as the
routes (ui D6), so the heatmap and the cards say the same thing. Low is the faintest, so the eye
goes to the weather that matters. The wind, rain and snow views colour each cell by that reading on
a continuous ramp of its own hue that reaches full strength at the reading's No Travel threshold,
with a legend in the reading's unit. They never use level colours, so a raw view is not mistaken
for risk, and they need no copy of the classification rules in the browser (D2).
Rejected: classifying single readings in the browser to colour the raw views by band, because it
would duplicate the graded rules D2 keeps on the server.
Enforced by: `frontend/src/corridor/colors.ts`; `colors.test.ts`.

### D7. Scrubbing is local: colours are precomputed per frame and blended between hours
When the corridor arrives, each view's colours are computed once for every frame, as one flat byte
array per frame. Moving the slider only blends the two frames either side of the slider's hour into
a reused array and hands it to the cell layer as a new colour attribute; nothing is fetched, parsed
or tessellated again. The slider moves in quarter hours (Page Up and Page Down jump three hours) and
Play runs the 48 hours in 16 seconds, so the weather visibly drifts between the hourly frames
instead of jumping. Each route's truck is drawn where its ETAs put it at the slider's hour,
interpolated between checkpoints, and waits at the destination once it has arrived.
Rejected: one deck.gl layer per frame toggled by visibility, because 49 layers of the same geometry
cost 49 times the GPU memory and cannot show the time between frames.
Enforced by: `frontend/src/corridor/colors.ts` (`frameColors`, `blendFrames`),
`frontend/src/corridor/truck.ts`, `frontend/src/corridor/Timeline.tsx`; `colors.test.ts`,
`truck.test.ts`.
