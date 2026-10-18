# Recommendation

Status: decided by Akhil, 2026-10-18. Issue: #6.

## North Star

Turn each route's classified checkpoints into a summary a driver can read ("12.4 Severe miles, 5 h
40 m") and pick the route the spec's preference order favours, with a reason that names what decided
it. The ranking must be reproducible from the summaries the UI shows, so a reviewer can check every
recommendation by hand.

Out of scope: choosing a departure time (`BACKLOG.md`).

## Decisions

### D1. Each checkpoint owns the stretch of road centred on it
The risk table classifies points; the ranking counts miles. A checkpoint owns the road from the
midpoint with its previous checkpoint to the midpoint with its next one. The first checkpoint's
stretch starts at the origin and the last one's ends at the destination, so owned miles always sum
to the route length, including a short final segment.
Rejected: each checkpoint owns the stretch ahead of it, because it shifts risk forward and gives the
destination checkpoint zero miles.
Rejected: checkpoint count × sampling interval, because the miles stop matching the route length on
the final partial segment.
Enforced by: `risk.scoring.owned_miles`; `test_owned_miles_sum_to_the_route_length`,
`test_owned_miles_centre_on_each_checkpoint`.

### D2. Miles at a level and the mean level are weighted by owned miles
"Miles at level" sums the owned miles of the checkpoints at that level. "Average risk" (ranking key 3)
is the mean of levels Low = 0 to No Travel = 4, weighted by owned miles. Weighting by miles makes the
mean independent of the sampling interval and comparable across routes of different lengths.
Rejected: a plain mean over checkpoints, because it depends on the interval and gives the short final
segment full weight.
Rejected: a mean weighted by time, because travel time is already ranking key 4 and would count twice.
Enforced by: `risk.scoring.summarize_route`; `test_mean_level_is_weighted_by_owned_miles`.

### D3. Routes rank by (No Travel miles, Severe miles, High miles, mean level, duration)
The spec's order is Severe miles, High miles, average risk, travel time. It never mentions No Travel,
the level it defines as worse than Severe. No Travel miles go first, so a route that crosses No Travel
can be shown and compared but never beats one that does not.
Rejected: disqualifying No Travel routes, because when every route crosses No Travel nothing would
remain to recommend.
Rejected: counting No Travel as Severe, because it throws away the one distinction the spec drew
above Severe.
Enforced by: `risk.recommendation.ranking_key`, `recommend`; `test_rank_*`.

### D4. Ranking keys compare at the precision the UI shows
Miles compare rounded to 0.1 mi, mean level to 0.01, and duration to the whole minute. A route never
wins on a difference the driver cannot see on the route cards, so two routes showing "3.2 Severe
miles" are tied on that key and the next key decides. Routes still tied on every key keep the routing
provider's order, which lists its preferred route first.
Rejected: comparing raw floats, because 0.0001 mi of floating-point difference would decide the
recommendation while the cards show identical numbers.
Enforced by: `risk.recommendation.ranking_key`; `test_differences_below_display_precision_tie`.

### D5. When every route crosses No Travel, recommend the least bad and say so
The top route is still recommended, and the result flags that every option crosses No Travel so the
UI can tell the driver to consider a later departure.
Rejected: returning no recommendation, because the driver still has to choose, and the ranking still
orders the options by how much No Travel and Severe road they cross.
Enforced by: `risk.recommendation.Recommendation.all_routes_cross_no_travel`;
`test_all_routes_crossing_no_travel_still_recommends_the_least_bad`.

### D6. The reason names the first key that separated the top two routes
The reason states the deciding key and both values: "Fewest Severe miles: 3.2 vs 18.5 on the next
best route." Keys that tied are not mentioned, so the reason never credits the winner with a
difference that did not matter.
Rejected: listing every metric of the winner, because it does not say why it won.
Enforced by: `risk.recommendation.recommend` (`decided_by`, `reason`); `test_reason_*`.

## Open questions

- Ties at display precision fall back to provider order. If that ever picks a visibly slower route,
  duration could move above mean level; the spec's order says otherwise, so it stays as written.
