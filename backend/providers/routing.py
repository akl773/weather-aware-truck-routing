"""Provider-neutral routes, and the plan that guarantees distinct options (routing D3 to D5)."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from providers.errors import NoRouteError
from providers.geo import Point, haversine_mi, interpolate, offset_point, overlap_share


@dataclass(frozen=True)
class Route:
    """A drivable route. `cum_mi[i]` and `cum_s[i]` are the miles and seconds to `points[i]`."""

    points: tuple[Point, ...]
    cum_mi: tuple[float, ...]
    cum_s: tuple[float, ...]
    # Set on fallback routes: the offset point the route was forced through.
    via: Point | None = None

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


def is_distinct(candidate: Route, kept: Sequence[Route]) -> bool:
    """False when more than 80% of `candidate` runs on a route already kept (routing D5)."""
    return all(overlap_share(candidate.points, route.points) <= MAX_OVERLAP for route in kept)


def plan_routes(router: Router, origin: Point, destination: Point, load_lb: float) -> list[Route]:
    """Up to three distinct routes: the provider's first, then via-point fallbacks (routing D4)."""
    kept: list[Route] = []
    for route in router.routes([origin, destination], load_lb, alternates=TARGET_ROUTES - 1):
        if is_distinct(route, kept):
            kept.append(route)

    span_mi = haversine_mi(origin, destination)
    if len(kept) < TARGET_ROUTES and span_mi >= MIN_FALLBACK_SPAN_MI:
        primary = kept[0]
        anchor = interpolate(primary.points, primary.cum_mi, primary.distance_mi / 2)
        for share in FALLBACK_OFFSETS:
            via = offset_point(anchor, origin, destination, share * span_mi)
            try:
                candidates = router.routes([origin, via, destination], load_lb, alternates=0)
            except NoRouteError:
                continue  # The via point found no road; try the next offset.
            for candidate in candidates:
                if is_distinct(candidate, kept):
                    kept.append(Route(candidate.points, candidate.cum_mi, candidate.cum_s, via))
            if len(kept) >= TARGET_ROUTES:
                break
    return kept[:TARGET_ROUTES]
