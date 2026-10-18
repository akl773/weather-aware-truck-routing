"""Provider-neutral routes, and the plan that guarantees distinct options (routing D3 to D5)."""

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Protocol

from providers.errors import NoRouteError, ProviderError
from providers.geo import Point, haversine_mi, interpolate, offset_point, overlap_share

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Route:
    """A drivable route. `cum_mi[i]` and `cum_s[i]` are the miles and seconds to `points[i]`."""

    points: tuple[Point, ...]
    cum_mi: tuple[float, ...]
    cum_s: tuple[float, ...]
    # Set on fallback routes: the offset point the route was forced through.
    via: Point | None = None
    # Any stretch the provider marks rough or unpaved.
    rough: bool = False

    @property
    def distance_mi(self) -> float:
        return self.cum_mi[-1]

    @property
    def duration_s(self) -> float:
        return self.cum_s[-1]


class Router(Protocol):
    def routes(self, stops: Sequence[Point], load_lb: float, alternates: int) -> list[Route]:
        """Routes through `stops` in order, the best first. Raises `NoRouteError`."""
        ...


TARGET_ROUTES = 3
MAX_OVERLAP = 0.8
# Via-point offsets as shares of the straight-line distance; positive is left of travel (D4).
FALLBACK_OFFSETS = (0.15, -0.15, 0.30, -0.30)
# Below this, an offset via point would be a detour around the block, not another route.
MIN_FALLBACK_SPAN_MI = 20.0
# A fallback slower than this multiple of the fastest route is a detour no dispatcher would offer.
MAX_FALLBACK_SLOWDOWN = 1.5
# No new fallback request starts after this long, so a plan stays inside the server's timeout.
FALLBACK_BUDGET_S = 20.0


def is_distinct(candidate: Route, kept: Sequence[Route]) -> bool:
    """False when more than 80% of either route runs on the other (routing D5).

    Both directions count: a candidate that is a kept route plus a detour contains all of it.
    """
    return all(
        max(
            overlap_share(candidate.points, route.points),
            overlap_share(route.points, candidate.points),
        )
        <= MAX_OVERLAP
        for route in kept
    )


def is_reasonable_fallback(candidate: Route, fastest: Route) -> bool:
    """A forced via point must not buy a route over rough roads or far slower than the best (D4)."""
    return (
        not candidate.rough and candidate.duration_s <= MAX_FALLBACK_SLOWDOWN * fastest.duration_s
    )


def plan_routes(
    router: Router,
    origin: Point,
    destination: Point,
    load_lb: float,
    clock: Callable[[], float] = time.monotonic,
) -> list[Route]:
    """Up to three distinct routes: the provider's own, then via-point fallbacks (routing D4)."""
    started = clock()
    kept: list[Route] = []
    for route in router.routes([origin, destination], load_lb, alternates=TARGET_ROUTES - 1):
        # Two places can snap to the same road point; a route with no length goes nowhere.
        if route.distance_mi > 0 and is_distinct(route, kept):
            kept.append(route)
    if not kept:
        raise NoRouteError("No truck route found between these places.")

    span_mi = haversine_mi(origin, destination)
    if len(kept) >= TARGET_ROUTES or span_mi < MIN_FALLBACK_SPAN_MI:
        return kept[:TARGET_ROUTES]

    fastest = min(kept, key=lambda r: r.duration_s)
    anchor = interpolate(kept[0].points, kept[0].cum_mi, kept[0].distance_mi / 2)
    for share in FALLBACK_OFFSETS:
        if len(kept) >= TARGET_ROUTES or clock() - started > FALLBACK_BUDGET_S:
            break
        via = offset_point(anchor, origin, destination, share * span_mi)
        # Rounded so the request, its cache key and its recording are stable across platforms.
        via = Point(round(via.lat, 6), round(via.lon, 6))
        try:
            candidates = router.routes([origin, via, destination], load_lb, alternates=0)
        except NoRouteError:
            continue  # The via point found no road; try the next offset.
        except ProviderError:
            # The routes in hand are still good; a failing fallback must not fail the plan.
            log.warning(
                "fallback route request failed; keeping %d routes", len(kept), exc_info=True
            )
            break
        for candidate in candidates:
            if is_reasonable_fallback(candidate, fastest) and is_distinct(candidate, kept):
                kept.append(replace(candidate, via=via))
    return kept[:TARGET_ROUTES]
