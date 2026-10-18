import itertools
import math
from dataclasses import replace

import pytest

from providers import routing
from providers.errors import NoRouteError, ProviderError
from providers.geo import Point, cumulative_mi
from providers.routing import Route, is_distinct, plan_routes

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
    """Answers the direct request with `direct`, then each via request with the next of `via`.

    A `via` entry that is an exception is raised instead.
    """

    def __init__(self, direct: list[Route], via: list[Route | Exception] | None = None):
        self.direct = direct
        self.via = via or []
        self.calls: list[list[Point]] = []

    def routes(self, stops, load_lb, alternates):
        self.calls.append(list(stops))
        if len(stops) == 2:
            return self.direct
        if not self.via:
            raise NoRouteError("no road near the via point")
        answer = self.via.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return [answer]


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


def point_east(miles: float) -> Point:
    return Point(40.0, -100.0 + miles / (69.17 * math.cos(math.radians(40.0))))


@pytest.mark.parametrize(("span_mi", "tries_fallback"), [(19.9, False), (20.1, True)])
def test_fallbacks_start_at_a_20_mile_straight_line(span_mi, tries_fallback):
    end = point_east(span_mi)
    assert cumulative_mi([ORIGIN, end])[-1] == pytest.approx(span_mi, abs=0.05)
    router = FakeRouter([route_through(ORIGIN, end)])
    plan_routes(router, ORIGIN, end, 30_000)
    assert (len(router.calls) > 1) is tries_fallback


@pytest.mark.parametrize(("share", "distinct"), [(0.79, True), (0.8, True), (0.81, False)])
def test_overlap_above_80_percent_is_the_same_option(monkeypatch, share, distinct):
    monkeypatch.setattr(routing, "overlap_share", lambda a, b: share)
    assert is_distinct(bend(30), [bend(0)]) is distinct


def test_a_route_plus_a_detour_is_not_a_new_option():
    # All of the primary runs on the candidate, even though the candidate is mostly detour.
    primary = route_through(ORIGIN, DESTINATION)
    loop = route_through(ORIGIN, DESTINATION, Point(40.5, -98.0), Point(40.5, -98.6), DESTINATION)
    assert not is_distinct(loop, [primary])


def test_rough_fallbacks_are_dropped():
    router = FakeRouter([bend(0), bend(30)], via=[replace(bend(-30), rough=True), bend(-40)])
    routes = plan_routes(router, ORIGIN, DESTINATION, 30_000)
    assert len(routes) == 3
    assert not any(r.rough for r in routes)


@pytest.mark.parametrize(("slowdown", "kept"), [(1.49, True), (1.51, False)])
def test_fallbacks_slower_than_1_5x_the_fastest_are_dropped(slowdown, kept):
    fastest = bend(0)
    slow = bend(30)
    slow = replace(
        slow, cum_s=tuple(s * slowdown * fastest.duration_s / slow.duration_s for s in slow.cum_s)
    )
    router = FakeRouter([fastest, bend(-30)], via=[slow])
    routes = plan_routes(router, ORIGIN, DESTINATION, 30_000)
    assert (len(routes) == 3) is kept


def test_a_failing_fallback_keeps_the_routes_in_hand():
    router = FakeRouter([bend(0), bend(30)], via=[ProviderError("rate limited"), bend(-30)])
    routes = plan_routes(router, ORIGIN, DESTINATION, 30_000)
    assert len(routes) == 2
    assert len(router.calls) == 2  # no more fallback requests after a provider failure


def test_fallbacks_stop_when_the_time_budget_is_spent():
    ticks = iter([0.0, 5.0, 25.0, 30.0])
    router = FakeRouter([bend(0)], via=[NoRouteError("none"), bend(30), bend(-30)])
    routes = plan_routes(router, ORIGIN, DESTINATION, 30_000, clock=lambda: next(ticks))
    assert len(routes) == 1
    assert len(router.calls) == 2  # the direct request and one fallback inside the budget


def test_an_empty_answer_is_no_route():
    with pytest.raises(NoRouteError):
        plan_routes(FakeRouter([]), ORIGIN, DESTINATION, 30_000)


NOWHERE = Route((ORIGIN, ORIGIN), (0.0, 0.0), (0.0, 0.0))


def test_a_route_with_no_length_is_dropped():
    routes = plan_routes(
        FakeRouter([NOWHERE, bend(0), bend(30), bend(-30)]), ORIGIN, DESTINATION, 30_000
    )
    assert NOWHERE not in routes
    assert len(routes) == 3


def test_only_routes_with_no_length_is_no_route():
    with pytest.raises(NoRouteError):
        plan_routes(FakeRouter([NOWHERE]), ORIGIN, DESTINATION, 30_000)


def test_via_points_are_rounded_to_6_decimals():
    router = FakeRouter([bend(0), bend(30)], via=[bend(-30)])
    plan_routes(router, ORIGIN, DESTINATION, 30_000)
    via = router.calls[1][1]
    assert via == Point(round(via.lat, 6), round(via.lon, 6))
