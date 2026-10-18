# Domain context

The words this codebase uses, with one meaning each. Code, tests, API fields and UI copy use these
terms. If a new concept needs a name, add it here in the same PR.

## Trip

- **Trip**: one planning request. Origin, destination, departure time, load weight and sampling
  interval.
- **Departure time**: when the truck leaves the origin. Stored timezone-aware in UTC; shown in the
  origin's local time.
- **Load weight**: gross load in pounds (lb). Only the load rules read it.
- **Sampling interval**: distance between checkpoints: 10, 25 or 50 miles.

## Routes

- **Route**: one option returned for a trip. A polyline plus driving time per span.
- **Span**: a stretch of polyline with its own driving duration, as the routing provider reports it.
  ETAs come from spans, not from an average speed.
- **Fallback route**: a route produced by routing through an offset via point, used when the provider
  returns fewer than three distinct routes.
- **Overlap**: the share of a route's length that runs on another route. Above 80% the two are the
  same option.

## Weather and risk

- **Checkpoint**: a point on a route, placed every sampling interval from the origin, plus the
  destination. Weather is read here.
- **ETA**: departure time plus the driving time to a checkpoint.
- **Forecast hour**: one hourly step of the weather forecast. Values at an ETA are interpolated
  between the two forecast hours around it.
- **Forecast horizon**: the last forecast hour the provider returns. A checkpoint past it has
  unknown weather and is never shown as Low.
- **Condition**: one of wind (sustained, mph), rain (in/hr) or snow (in/hr).
- **Band**: the class of one condition from the risk table: Low, Moderate, High, Severe or No Travel.
- **Load rules**: the spec's wind-and-weight rules that raise the wind band for heavy loads.
- **Level**: a checkpoint's final class, the worst band after load rules. Ordered Low (0), Moderate
  (1), High (2), Severe (3), No Travel (4).
- **Driver condition**: a condition whose band equals the checkpoint's level. Ties name every one.
  Shown with its reading, e.g. "snow 2.4 in/hr".
- **Gust flag**: marks a checkpoint where gusts reach a higher wind band than sustained wind. It
  informs the driver and never changes the level.

## Scoring

- **Owned miles**: the stretch of route a checkpoint speaks for: half the distance to each
  neighbouring checkpoint. Owned miles on a route sum to its length.
- **Miles at level**: owned miles summed per level, e.g. "12 Severe miles".
- **Mean level**: the owned-mile-weighted average of checkpoint levels on a route (0 to 4).
- **Route summary**: miles at each level, mean level, distance and driving time.
- **Recommendation**: the route that ranks first, with a plain-language reason.

## Corridor

- **Corridor**: the area within 40 km of any route of the trip.
- **Cell**: one square of the grid covering the corridor, about 15 km across.
- **Frame**: weather for every cell at one forecast hour. The heatmap holds 48 frames, hour 0 being
  the departure time.
- **Truck marker**: where the truck would be on each route at the slider's hour.

## Terms we avoid

- "Score" for anything the spec calls a level or a band. The ranking compares miles and levels, so
  there is no single number.
- "Safe". The app ranks relative risk and cannot certify a route as safe.
- "Heatmap" for density rendering. Our heatmap is a grid of classified cells.
