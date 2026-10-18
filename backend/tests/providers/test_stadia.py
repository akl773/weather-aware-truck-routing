import itertools
import json
import logging

import httpx
import pytest

from providers.errors import NoRouteError, ProviderError
from providers.geo import Point, haversine_mi
from providers.routing import Route, plan_routes
from providers.stadia import BASE_URL, StadiaMaps, gross_weight_tonnes, parse_trip
from tests.providers.replay import FIXTURES, replay_client
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


def maps_answering(answer: httpx.Response | Exception) -> StadiaMaps:
    def handler(request: httpx.Request) -> httpx.Response:
        if isinstance(answer, Exception):
            raise answer
        return answer

    return StadiaMaps(httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler)), "k")


def denver_salt_lake_city_primary() -> Route:
    adapter = maps("stadia_route_denver_salt_lake_city")
    return adapter.routes([DENVER, SALT_LAKE_CITY], LOAD_LB, 2)[0]


def recorded_summary(fixture: str) -> dict:
    recording = json.loads((FIXTURES / f"{fixture}.json").read_text())
    return recording[0]["response"]["body"]["trip"]["summary"]


def encode_polyline(points: list[Point], precision: int = 6) -> str:
    out, prev = [], (0, 0)
    for p in points:
        cur = (round(p.lat * 10**precision), round(p.lon * 10**precision))
        for delta in (cur[0] - prev[0], cur[1] - prev[1]):
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 0x20:
                out.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            out.append(chr(value + 63))
        prev = cur
    return "".join(out)


def leg(*points: Point, rough: bool = False) -> dict:
    """A two-point Valhalla leg: one 10-mile, 10-minute maneuver and the arrival."""
    drive = {"begin_shape_index": 0, "end_shape_index": 1, "length": 10.0, "time": 600.0}
    if rough:
        drive["rough"] = True
    arrive = {"begin_shape_index": 1, "end_shape_index": 1, "length": 0.0, "time": 0.0}
    return {"shape": encode_polyline(list(points)), "maneuvers": [drive, arrive]}


A, B, C = Point(38.5, -120.2), Point(38.6, -120.2), Point(38.7, -120.2)


# --- Weight (routing D2) -------------------------------------------------------------------------


def test_gross_weight_adds_the_tractor_trailer():
    # 35,000 lb rig + 45,000 lb load = 80,000 lb, the US federal gross limit, = 36.29 t.
    assert gross_weight_tonnes(45_000) == 36.29


def test_empty_trailer_still_weighs_the_rig():
    assert gross_weight_tonnes(0) == 15.88


# --- Parsing (routing D3) ------------------------------------------------------------------------


def test_cumulative_values_end_at_the_provider_totals():
    route = denver_salt_lake_city_primary()
    summary = recorded_summary("stadia_route_denver_salt_lake_city")
    # Maneuver lengths are rounded to 0.001 mi by the provider, so their sum drifts a little.
    assert route.distance_mi == pytest.approx(summary["length"], abs=0.1)
    assert route.duration_s == pytest.approx(summary["time"], abs=1)
    assert len(route.points) == len(route.cum_mi) == len(route.cum_s)
    assert route.points[0] == pytest.approx(DENVER, abs=0.05)
    assert route.points[-1] == pytest.approx(SALT_LAKE_CITY, abs=0.05)


def test_cumulative_values_never_decrease():
    route = denver_salt_lake_city_primary()
    assert all(b >= a for a, b in itertools.pairwise(route.cum_mi))
    assert all(b >= a for a, b in itertools.pairwise(route.cum_s))


def test_cumulative_miles_track_the_drawn_shape():
    # Spreading maneuver lengths over shape points must not distort distance along the line.
    route = denver_salt_lake_city_primary()
    drawn = sum(haversine_mi(a, b) for a, b in itertools.pairwise(route.points))
    assert route.distance_mi == pytest.approx(drawn, rel=0.01)


def test_multi_leg_trip_keeps_the_joining_point_once():
    route = parse_trip({"legs": [leg(A, B), leg(B, C)]})
    assert route.points == (A, B, C)
    assert route.cum_mi == (0.0, 10.0, 20.0)
    assert route.cum_s == (0.0, 600.0, 1200.0)


def test_a_rough_maneuver_marks_the_route_rough():
    assert parse_trip({"legs": [leg(A, B, rough=True)]}).rough
    assert not parse_trip({"legs": [leg(A, B)]}).rough


# --- Requests ------------------------------------------------------------------------------------


def test_three_provider_routes_come_back_in_one_request():
    adapter = maps("stadia_route_denver_salt_lake_city")
    routes = plan_routes(adapter, DENVER, SALT_LAKE_CITY, LOAD_LB)
    assert len(routes) == 3
    assert all(r.via is None for r in routes)


def test_two_provider_routes_and_a_fallback():
    routes = plan_routes(maps("stadia_route_atlanta_charlotte"), ATLANTA, CHARLOTTE, LOAD_LB)
    assert [r.via is None for r in routes] == [True, True, False]


def test_one_provider_route_and_two_fallbacks():
    routes = plan_routes(maps("stadia_route_dallas_houston"), DALLAS, HOUSTON, LOAD_LB)
    assert [r.via is None for r in routes] == [True, False, False]


@pytest.mark.parametrize(
    ("fixture", "origin", "destination"),
    [
        ("stadia_route_atlanta_charlotte", ATLANTA, CHARLOTTE),
        ("stadia_route_dallas_houston", DALLAS, HOUSTON),
    ],
)
def test_recorded_fallbacks_are_paved_and_within_1_5x_the_fastest(fixture, origin, destination):
    routes = plan_routes(maps(fixture), origin, destination, LOAD_LB)
    fastest = min(r.duration_s for r in routes)
    assert not any(r.rough for r in routes)
    assert all(r.duration_s <= 1.5 * fastest for r in routes)


def test_via_points_ask_for_a_secondary_road_or_better():
    sent = []

    def handler(request):
        sent.append(json.loads(request.content))
        return httpx.Response(400, json={"error_code": 442})

    client = httpx.Client(base_url=BASE_URL, transport=httpx.MockTransport(handler))
    with pytest.raises(NoRouteError):
        StadiaMaps(client, "k").routes([DALLAS, Point(31.5, -96.5), HOUSTON], LOAD_LB, 0)
    origin, via, destination = sent[0]["locations"]
    assert origin["type"] == destination["type"] == "break"
    assert via["type"] == "through"
    assert via["search_filter"] == {"min_road_class": "secondary"}


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
        maps_answering(httpx.ReadTimeout("slow")).routes([DENVER, SALT_LAKE_CITY], 0, 2)


def test_rate_limit_is_a_provider_error():
    with pytest.raises(ProviderError, match="rate limiting"):
        maps_answering(httpx.Response(429)).routes([DENVER, SALT_LAKE_CITY], 0, 2)


def test_bad_key_is_a_provider_error_not_a_missing_route():
    answer = httpx.Response(401, json={"error": "Invalid API key"})
    with pytest.raises(ProviderError, match="failed to answer"):
        maps_answering(answer).routes([DENVER, SALT_LAKE_CITY], 0, 2)


@pytest.mark.parametrize(
    "answer",
    [
        httpx.Response(200, text="<html>gateway</html>"),
        httpx.Response(200, json={"no": "trip"}),
        httpx.Response(200, json={"trip": {"legs": [{"shape": 5}]}}),
        httpx.Response(400, json=["not", "an", "object"]),
    ],
)
def test_unreadable_answers_are_provider_errors(answer):
    with pytest.raises(ProviderError):
        maps_answering(answer).routes([DENVER, SALT_LAKE_CITY], 0, 2)


# --- Places (routing D6) -------------------------------------------------------------------------


def test_autocomplete_returns_labels_and_coordinates():
    places = maps("stadia_places_denv").autocomplete("Denv")
    assert places[0].label == "Denver, CO, USA"
    assert places[0].point == pytest.approx(DENVER, abs=0.05)


def test_unreadable_place_answer_is_a_provider_error():
    with pytest.raises(ProviderError):
        maps_answering(httpx.Response(200, json={"features": [{}]})).autocomplete("Denv")


# --- Secrets -------------------------------------------------------------------------------------


def test_request_urls_with_the_key_are_never_logged_at_info():
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING
