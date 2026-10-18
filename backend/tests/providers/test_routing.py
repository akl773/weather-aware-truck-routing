import itertools
import math

import pytest

from providers.errors import NoRouteError
from providers.geo import Point, cumulative_mi
from providers.routing import Route, plan_routes

ORIGIN = Point(40.0, -100.0)
DESTINATION = Point(40.0, -98.0)  # ~106 miles due east


def route_through(*stops: Point, step_mi: float = 1.0) -> Route:
    """A route of straight segments through `stops`, driven at 60 mph."""
    points = [stops[0]]
    for a, b in itertools.pairwise(stops):
        dist = cumulative_mi([a, b])[-1]
        count = max(1, math.ceil(dist / step_mi))
        points += [
            Point(a.lat + (b.lat - a.lat) * k / count, a.lon + (b.lon - a.lon) * k / count)
            for k in range(1, count + 1)
        ]
    cum = cumulative_mi(points)
    return Route(tuple(points), tuple(cum), tuple(m * 60 for m in cum))


def bend(lat_offset_mi: float) -> Route:
    """Origin to destination through a point north (or south) of the midpoint."""
    return route_through(ORIGIN, Point(40.0 + lat_offset_mi / 69.0, -99.0), DESTINATION)


class FakeRouter:
    def __init__(self, direct: list[Route], via: list[Route] | None = None):
        self.direct = direct
        self.via = via or []
        self.calls: list[list[Point]] = []

    def routes(self, stops, load_lb, alternates):
        self.calls.append(list(stops))
        if len(stops) == 2:
            return self.direct
        if not self.via:
            raise NoRouteError("no road near the via point")
        return [self.via.pop(0)]


def test_three_distinct_provider_routes_need_no_fallback():
    router = FakeRouter([bend(0), bend(30), bend(-30)])
    assert len(plan_routes(router, ORIGIN, DESTINATION, 30_000)) == 3
    assert len(router.calls) == 1


def test_two_provider_routes_get_a_fallback_third():
    router = FakeRouter([bend(0), bend(30)], via=[bend(-30)])
    routes = plan_routes(router, ORIGIN, DESTINATION, 30_000)
    assert len(routes) == 3
    assert [r.via is None for r in routes] == [True, True, False]
    assert len(router.calls[1]) == 3  # origin, via, destination


def test_one_provider_route_gets_two_fallbacks():
    router = FakeRouter([bend(0)], via=[bend(30), bend(-30)])
    assert len(plan_routes(router, ORIGIN, DESTINATION, 30_000)) == 3


def test_routes_sharing_more_than_80_percent_are_one_option():
    # A provider alternate that is the primary route plus a sliver is not a second option.
    router = FakeRouter([bend(0), bend(0.1)], via=[bend(0.05), bend(30), bend(-30)])
    routes = plan_routes(router, ORIGIN, DESTINATION, 30_000)
    assert len(routes) == 3
    assert [r.via is None for r in routes] == [True, False, False]


def test_fallback_skips_via_points_with_no_road():
    router = FakeRouter([bend(0)])
    routes = plan_routes(router, ORIGIN, DESTINATION, 30_000)
    assert len(routes) == 1
    assert len(router.calls) == 5  # the direct request and all four offsets


def test_first_fallback_offset_is_left_of_travel_at_15_percent():
    router = FakeRouter([bend(0), bend(30)], via=[bend(-30)])
    plan_routes(router, ORIGIN, DESTINATION, 30_000)
    via = router.calls[1][1]
    straight_line_mi = cumulative_mi([ORIGIN, DESTINATION])[-1]
    # Travel is due east, so left is north.
    assert (via.lat - 40.0) * 69.0 == pytest.approx(0.15 * straight_line_mi, rel=0.02)


def test_short_trips_get_no_fallback():
    near = Point(40.0, -99.9)  # ~5 miles away
    router = FakeRouter([route_through(ORIGIN, near)])
    assert len(plan_routes(router, ORIGIN, near, 30_000)) == 1
    assert len(router.calls) == 1
