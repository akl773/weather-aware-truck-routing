# UI

Status: decided by Akhil, 2026-10-19. Issues: #12 (trip form), #13 (routes and cards).

## North Star
A dispatcher plans a trip and understands the answer at a glance: which route, why, and where the
weather bites. Everything the spec asks for (routes, checkpoints, levels, ETAs, summaries, the
corridor over 48 hours) is on one screen, readable without dev tools, usable from the keyboard, and
never sends the API a request it would reject.
Out of scope: accounts, saved trips, printing and native mobile apps.

## Decisions

### D1. One screen: the map, a floating panel, and a timeline
The map fills the window. A panel floats on the left with the trip form, then the recommendation and
the route cards; the timeline sits along the bottom once there is a plan. Nothing navigates away, so
the map never reloads and the route a card describes is always visible beside it. Below 720 px wide
the panel spans the width at the top and scrolls on its own.
Rejected: a form page that leads to a results page, because comparing routes needs the map and the
cards side by side.
Enforced by: `frontend/src/App.tsx`, `frontend/src/layout/Panel.tsx`.

### D2. Places come only from suggestions
The origin and destination fields search `/api/places` as the user types (two characters or more,
after a 250 ms pause, up to the API's 100) and hold a place only once one is picked. Typing again
clears the pick but keeps the text, so the coordinates sent always belong to the label shown (routing
D6). Suggestions for text the user has since changed stay visible but cannot be picked, so Enter
never takes a place that does not match what was typed. Suggestions are cached per query for five
minutes.
Rejected: geocoding free text on submit, because a typo would silently plan a trip to the wrong
town.
Enforced by: `frontend/src/trip/PlaceField.tsx`.

### D3. Departure is entered and shown in the browser's time zone
The departure field is the browser's native date-and-time input, which is keyboard accessible and
localised. It defaults to the next full hour and is sent with the browser's UTC offset, so the API
receives an exact instant (plan-api D1). Every time the app shows (ETAs, slider hours) is in the same
zone, and the zone's short name at the chosen departure is printed next to the field. A time the
clocks skip in spring is rejected rather than silently moved an hour.
Rejected: showing each checkpoint in the time zone it lies in, because a trip across zones would
show the truck arriving before it left.
Enforced by: `frontend/src/trip/draft.ts` (`toOffsetIso`), `frontend/src/format.ts`;
`draft.test.ts`.

### D4. The form checks every bound the API checks before it sends anything
Places picked and at least a mile apart, a departure from an hour ago to seven days ahead, a whole
load from 0 to 80,000 lb, and an interval of 10, 25 or 50 miles: the same bounds as plan-api D1.
Errors show under their field once the user tries to submit, and the first invalid field takes
focus. The API stays the authority; its errors appear above the button in its own words.
Rejected: relying on the API's 400s alone, because a round trip per mistake is slow and the
acceptance criteria forbid sending invalid input.
Enforced by: `frontend/src/trip/draft.ts` (`validateTrip`); `draft.test.ts`.

### D5. A plan is cached per trip and never retried automatically
The plan is a query keyed by the exact request, so planning the same trip again within ten minutes
shows the cached answer at once. A failed plan is not retried: a 4xx will fail the same way, and a
retry after a weather rate limit (weather D4) only spends more of the budget the user is waiting on.
Nor does the plan refetch on window focus or reconnect, which would resend a departure that may have
passed. The user retries with the button, which also fetches a fresh plan for an identical trip once
the cached one is ten minutes old.
Rejected: a mutation, because it caches nothing and two clicks would plan twice.
Enforced by: `frontend/src/plan/usePlan.ts`.

### D6. Routes are drawn in their checkpoints' levels, and the selected route sits on top
Each route is cut into pieces by the miles each checkpoint owns, the same stretches the summary
counts (risk scoring), and each piece takes its checkpoint's level colour: green Low, yellow
Moderate, orange High, red Severe, purple No Travel, grey Unknown. Neighbouring levels differ in
lightness as well as hue, and every level is also written as a word in the cards, tooltip and list,
so colour is never the only cue. The selected route is drawn last, wider, at full opacity and on a white casing;
the others stay visible at about half opacity for comparison. A letter at each route's midpoint names it,
and the trip ends are drawn as a hollow start and a solid finish.
Rejected: one colour per route, because the map would then show which route is which but not where
the weather bites, which is the question the dispatcher has.
Enforced by: `frontend/src/plan/segments.ts`, `frontend/src/map/planLayers.ts`,
`frontend/src/risk/levels.ts`; `segments.test.ts`.

### D7. The cards, the map and the checkpoint list share one selection
A new plan selects its recommended route. Choosing a route on its card or on the map selects it in
both, and the checkpoint list below the cards shows that route's checkpoints. Hovering a checkpoint
on the map shows its mile, ETA, level and readings; hovering or focusing a row in the list
highlights the same checkpoint on the map, so the list is the keyboard way to the same detail. Once
a plan arrives the form collapses to a one-line summary and focus moves to the plan; "Edit" brings
the form back with focus in its first field.
Rejected: a separate detail panel per checkpoint, because it hides the map the detail is about.
Enforced by: `frontend/src/App.tsx`, `frontend/src/plan/RouteCards.tsx`,
`frontend/src/plan/CheckpointList.tsx`, `frontend/src/map/CheckpointTooltip.tsx`.
