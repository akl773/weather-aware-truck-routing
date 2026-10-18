import itertools
import logging

import httpx
import pytest

from providers.errors import NoRouteError, ProviderError
from providers.geo import haversine_mi
from providers.routing import plan_routes
from providers.stadia import BASE_URL, StadiaMaps, gross_weight_tonnes, parse_trip
from tests.providers.replay import replay_client
from tests.providers.scenarios import (
    ATLANTA,
    BACKCOUNTRY,
    CHARLOTTE,
    DALLAS,
    DENVER,
    HOUSTON,
    LOAD_LB,
    SALT_LAKE_CITY,
)


def maps(fixture: str) -> StadiaMaps:
    return StadiaMaps(replay_client(fixture, BASE_URL), "test-key")


def denver_salt_lake_city_primary():
    adapter = maps("stadia_route_denver_salt_lake_city")
    return adapter.routes([DENVER, SALT_LAKE_CITY], LOAD_LB, 2)[0]


def maps_answering(status: int, body: dict | None = None, error: Exception | None = None):
    def handler(request: httpx.Request) -> httpx.Response:
        if error:
            raise error
        return httpx.Response(status, json=body or {})

    return StadiaMaps(httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler)), "k")


# --- Weight (routing D2) -------------------------------------------------------------------------


def test_gross_weight_adds_the_tractor_trailer():
    # 35,000 lb rig + 45,000 lb load = 80,000 lb, the US federal gross limit, = 36.29 t.
    assert gross_weight_tonnes(45_000) == 36.29


def test_empty_trailer_still_weighs_the_rig():
    assert gross_weight_tonnes(0) == 15.88


# --- Parsing (routing D3) ------------------------------------------------------------------------


def test_cumulative_values_end_at_the_provider_totals():
    route = maps("stadia_route_denver_salt_lake_city").routes([DENVER, SALT_LAKE_CITY], LOAD_LB, 2)[
        0
    ]
    assert route.distance_mi == pytest.approx(521.6, abs=1)
    assert len(route.points) == len(route.cum_mi) == len(route.cum_s)
    assert route.points[0] == pytest.approx(DENVER, abs=0.05)
    assert route.points[-1] == pytest.approx(SALT_LAKE_CITY, abs=0.05)


def test_cumulative_values_never_decrease():
    route = maps("stadia_route_denver_salt_lake_city").routes([DENVER, SALT_LAKE_CITY], LOAD_LB, 2)[
        0
    ]
    assert all(b >= a for a, b in itertools.pairwise(route.cum_mi))
    assert all(b >= a for a, b in itertools.pairwise(route.cum_s))


def test_cumulative_miles_track_the_drawn_shape():
    # Spreading maneuver lengths over shape points must not distort distance along the line.
    route = maps("stadia_route_denver_salt_lake_city").routes([DENVER, SALT_LAKE_CITY], LOAD_LB, 2)[
        0
    ]
    drawn = sum(haversine_mi(a, b) for a, b in itertools.pairwise(route.points))
    assert route.distance_mi == pytest.approx(drawn, rel=0.01)


def test_multi_leg_trip_keeps_the_joining_point_once():
    leg = {
        "shape": "_izlhA~rlgdF_{geC~ywl@",  # two points
        "maneuvers": [
            {"begin_shape_index": 0, "end_shape_index": 1, "length": 10.0, "time": 600.0},
            {"begin_shape_index": 1, "end_shape_index": 1, "length": 0.0, "time": 0.0},
        ],
    }
    second = {**leg, "shape": "_{geC~ywl@_kwzCn`{nI"}  # starts where the first ends
    route = parse_trip({"legs": [leg, second]})
    assert len(route.points) == 3
    assert route.cum_mi == (0.0, 10.0, 20.0)
    assert route.cum_s == (0.0, 600.0, 1200.0)


# --- Requests ------------------------------------------------------------------------------------


def test_three_provider_routes_come_back_in_one_request():
    routes = plan_routes(
        maps("stadia_route_denver_salt_lake_city"), DENVER, SALT_LAKE_CITY, LOAD_LB
    )
    assert len(routes) == 3
    assert all(r.via is None for r in routes)


def test_two_provider_routes_and_a_fallback():
    routes = plan_routes(maps("stadia_route_atlanta_charlotte"), ATLANTA, CHARLOTTE, LOAD_LB)
    assert [r.via is None for r in routes] == [True, True, False]


def test_one_provider_route_and_two_fallbacks():
    routes = plan_routes(maps("stadia_route_dallas_houston"), DALLAS, HOUSTON, LOAD_LB)
    assert [r.via is None for r in routes] == [True, False, False]


def test_fallback_routes_are_longer_than_the_primary():
    routes = plan_routes(maps("stadia_route_dallas_houston"), DALLAS, HOUSTON, LOAD_LB)
    assert routes[1].distance_mi > routes[0].distance_mi
    assert routes[2].distance_mi > routes[0].distance_mi


def test_no_path_raises_no_route_error():
    with pytest.raises(NoRouteError, match="No truck route"):
        maps("stadia_route_no_path").routes([DENVER, BACKCOUNTRY], LOAD_LB, 2)


def test_a_second_identical_request_is_served_from_the_cache():
    calls = []

    def handler(request):
        calls.append(request)
        return replay_client("stadia_route_denver_salt_lake_city", BASE_URL).send(request)

    client = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    adapter = StadiaMaps(client, "test-key")
    adapter.routes([DENVER, SALT_LAKE_CITY], LOAD_LB, 2)
    adapter.routes([DENVER, SALT_LAKE_CITY], LOAD_LB, 2)
    assert len(calls) == 1


# --- Failures ------------------------------------------------------------------------------------


def test_timeout_is_a_provider_error():
    with pytest.raises(ProviderError, match="could not be reached"):
        maps_answering(0, error=httpx.ReadTimeout("slow")).routes([DENVER, SALT_LAKE_CITY], 0, 2)


def test_rate_limit_is_a_provider_error():
    with pytest.raises(ProviderError, match="rate limiting"):
        maps_answering(429).routes([DENVER, SALT_LAKE_CITY], 0, 2)


def test_bad_key_is_a_provider_error_not_a_missing_route():
    with pytest.raises(ProviderError, match="failed to answer"):
        maps_answering(401, {"error": "Invalid API key"}).routes([DENVER, SALT_LAKE_CITY], 0, 2)


# --- Places (routing D6) -------------------------------------------------------------------------


def test_autocomplete_returns_labels_and_coordinates():
    places = maps("stadia_places_denv").autocomplete("Denv")
    assert places[0].label == "Denver, CO, USA"
    assert places[0].point == pytest.approx(DENVER, abs=0.05)


# --- Secrets -------------------------------------------------------------------------------------


def test_request_urls_with_the_key_are_never_logged_at_info():
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
