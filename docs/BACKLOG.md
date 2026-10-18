# Backlog

Ideas considered and deliberately not built. The brief asks for correctness and clarity over extra
features, so each entry says why it waits. Agents do not build these unless asked.

| Idea | Why it waits |
|---|---|
| Best departure time ("leave at 06:00 to avoid the storm") | The most useful extension: re-run the ranking for departures across the 48 h window. It changes the product question from "which route" to "which route and when", which is beyond the brief. |
| Saved trips and shareable links | Needs persistence and identity. The app is stateless by decision (`stack.md`). |
| Truck restrictions beyond weight (height, hazmat, axle count) | Valhalla's truck costing supports them, but the brief's only vehicle input is load weight. |
| Hours-of-service rest stops in the ETA | Real trips over about 11 driving hours include mandatory breaks, which shift every later ETA. Modelling HOS rules properly is its own project. |
| Official weather alerts overlay (NWS warning polygons) | Valuable context, but US-only and outside the risk table the brief defines. |
| Visibility, freezing rain and road-surface ice | Real hazards for trucks with no thresholds in the brief. Adding them would invent rules. |
| Live re-planning while driving | Needs live position and push updates; the app plans before departure. |
