import math
from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

import trips.plan
from providers import open_meteo, stadia
from providers.errors import ProviderError
from providers.geo import Point, cumulative_mi
from providers.open_meteo import Series
from providers.routing import Route
from tests.providers.replay import replay_client
from tests.providers.scenarios import (
    BACKCOUNTRY,
    DENVER,
    LOAD_LB,
    PLAN_DEPARTURE,
    PLAN_INTERVAL_MI,
    PLAN_NOW,
    PLAN_WEATHER_FIXTURE,
    SALT_LAKE_CITY,
)
from trips.serializers import PlanRequestSerializer


@pytest.fixture(autouse=True)
def frozen(monkeypatch):
    cache.clear()
    monkeypatch.setattr(timezone, "now", lambda: PLAN_NOW)
    yield
    cache.clear()


def recorded(monkeypatch, route_fixture="stadia_route_denver_salt_lake_city"):
    maps = stadia.StadiaMaps(replay_client(route_fixture, stadia.BASE_URL), "test-key")
    weather = open_meteo.OpenMeteo(replay_client(PLAN_WEATHER_FIXTURE, open_meteo.BASE_URL))
    monkeypatch.setattr(stadia, "default", lambda: maps)
    monkeypatch.setattr(open_meteo, "default", lambda: weather)


def place(label, point):
    return {"label": label, "lat": point.lat, "lon": point.lon}


def trip(**changes):
    body = {
        "origin": place("Denver, CO, USA", DENVER),
        "destination": place("Salt Lake City, UT, USA", SALT_LAKE_CITY),
        "departure": PLAN_DEPARTURE.isoformat(),
        "load_lb": LOAD_LB,
        "interval_mi": PLAN_INTERVAL_MI,
    }
    return body | changes


def post(body):
    return Client().post("/api/plan", body, content_type="application/json")


def valid(**changes) -> bool:
    return PlanRequestSerializer(data=trip(**changes), context={"now": PLAN_NOW}).is_valid()


# --- Happy path ----------------------------------------------------------------------------------


def test_plan_returns_three_ranked_routes(monkeypatch):
    recorded(monkeypatch)
    body = post(trip()).json()
    assert [r["id"] for r in body["routes"]] == ["A", "B", "C"]
    assert sorted(body["recommendation"]["ranking"]) == ["A", "B", "C"]
    assert body["recommendation"]["route_id"] == body["recommendation"]["ranking"][0]
    assert body["weather"] == {"start": "2026-10-19T11:00:00Z", "hours": 72}


def test_checkpoints_carry_eta_readings_level_and_owned_stretch(monkeypatch):
    recorded(monkeypatch)
    checkpoint = post(trip()).json()["routes"][0]["checkpoints"][1]
    assert checkpoint["mile"] == 25.0
    assert checkpoint["eta"].endswith("Z")
    assert set(checkpoint["readings"]) == {"wind_mph", "gust_mph", "rain_in_hr", "snow_in_hr"}
    assert checkpoint["level"] in range(5)
    assert checkpoint["owned_from_mi"] == 12.5
    assert checkpoint["owned_to_mi"] == 37.5


def assert_numbers_are_shown_values(body):
    for route in body["routes"]:
        summary = route["summary"]
        for miles in summary["miles_by_level"].values():
            assert miles == round(miles, 1)
        assert sum(summary["miles_by_level"].values()) == pytest.approx(
            summary["distance_mi"], abs=0.3
        )
        for checkpoint in route["checkpoints"]:
            for name, places in PLACES.items():
                value = checkpoint["readings"][name]
                assert value is None or value == round(value, places)


PLACES = {"wind_mph": 1, "gust_mph": 1, "rain_in_hr": 2, "snow_in_hr": 2}


def test_response_numbers_are_the_numbers_shown(monkeypatch):
    recorded(monkeypatch)
    assert_numbers_are_shown_values(post(trip()).json())


def test_an_offset_departure_is_read_as_the_same_instant(monkeypatch):
    recorded(monkeypatch)
    mountain = PLAN_DEPARTURE.astimezone(timezone.get_fixed_timezone(-360)).isoformat()
    assert post(trip(departure=mountain)).json() == post(trip()).json()


def test_interval_defaults_to_25_miles(monkeypatch):
    recorded(monkeypatch)
    body = trip()
    del body["interval_mi"]
    assert post(body).json()["routes"][0]["checkpoints"][1]["mile"] == 25.0


# --- Mixed weather, end to end --------------------------------------------------------------------


def straight_route(lon: float, via: Point | None = None) -> Route:
    """About 100 miles due north at `lon`, driven in two hours."""
    points = tuple(Point(40.0 + 1.45 * i / 100, lon) for i in range(101))
    cum_mi = tuple(cumulative_mi(points))
    return Route(points, cum_mi, tuple(m / cum_mi[-1] * 7200 for m in cum_mi), via=via)


# One kind of weather per route, keyed by its longitude.
WEATHER_BY_LON = {
    -100.0: dict(wind=30.0, gust=31.0, rain=0.0),  # Moderate wind
    -101.0: dict(wind=10.0, gust=40.0, rain=0.6),  # Severe rain, gusty
    -102.0: dict(wind=10.0, gust=12.0, rain=None),  # no rain forecast: unknown
}


class MixedWeather:
    def hourly(self, points, start, hours):
        times = tuple(start.timestamp() + 3600 * k for k in range(hours))
        result = {}
        for p in points:
            w = WEATHER_BY_LON[p.lon]
            result[p] = Series(
                times,
                (w["wind"],) * hours,
                (w["gust"],) * hours,
                (w["rain"],) * hours,
                (0.0,) * hours,
            )
        return result


@pytest.fixture
def mixed_plan(monkeypatch):
    routes = [
        straight_route(-100.0),
        straight_route(-101.0, via=Point(40.7, -101.0)),
        straight_route(-102.0),
    ]
    monkeypatch.setattr(trips.plan, "plan_routes", lambda *args: routes)
    monkeypatch.setattr(stadia, "default", lambda: None)
    monkeypatch.setattr(open_meteo, "default", MixedWeather)
    response = post(trip())
    assert response.status_code == 200
    return response.json()


def test_mixed_weather_ranks_by_the_first_key_that_differs(mixed_plan):
    assert mixed_plan["recommendation"]["ranking"] == ["A", "B", "C"]
    assert mixed_plan["recommendation"]["decided_by"] == "severe_miles"


def test_mixed_weather_carries_level_drivers_and_gusts(mixed_plan):
    a, b, _ = mixed_plan["routes"]
    assert {c["level"] for c in a["checkpoints"]} == {1}
    assert a["checkpoints"][0]["drivers"] == ["wind"]
    assert b["checkpoints"][0]["level"] == 3
    assert b["checkpoints"][0]["drivers"] == ["rain"]
    assert b["checkpoints"][0]["gusty"] is True
    assert b["fallback"] is True
    assert a["fallback"] is False


def test_unknown_weather_reaches_the_response_as_null(mixed_plan):
    c = mixed_plan["routes"][2]
    assert all(cp["level"] is None for cp in c["checkpoints"])
    assert c["checkpoints"][0]["readings"]["rain_in_hr"] is None
    assert c["checkpoints"][0]["readings"]["wind_mph"] == 10.0
    assert c["summary"]["miles_by_level"]["unknown"] == c["summary"]["distance_mi"]
    assert c["summary"]["mean_level"] is None
    assert_numbers_are_shown_values(mixed_plan)


# --- Input (plan-api D1) -------------------------------------------------------------------------


def test_plan_rejects_a_departure_without_an_offset():
    response = post(trip(departure="2026-10-19T12:00:00"))
    assert response.status_code == 400
    assert "departure" in response.json()["fields"]


@pytest.mark.parametrize(
    "departure",
    ["2026-13-45T00:00:00Z", "2026-02-30T12:00:00+00:00", "2026-10-19T12:00:00+25:00", "soon"],
)
def test_plan_rejects_a_departure_that_is_not_a_date(departure):
    response = post(trip(departure=departure))
    assert response.status_code == 400
    assert "departure" in response.json()["fields"]


def test_plan_rejects_a_naive_datetime_from_python():
    naive = PLAN_DEPARTURE.replace(tzinfo=None)
    assert not PlanRequestSerializer(
        data=trip(departure=naive), context={"now": PLAN_NOW}
    ).is_valid()


@pytest.mark.parametrize(
    "offset",
    [-timedelta(hours=1, seconds=1), timedelta(days=7, seconds=1)],
    ids=["over_an_hour_ago", "over_7_days_ahead"],
)
def test_plan_rejects_a_departure_outside_the_window(offset):
    response = post(trip(departure=(PLAN_NOW + offset).isoformat()))
    assert response.status_code == 400
    assert "departure" in response.json()["fields"]


@pytest.mark.parametrize(
    "offset", [-timedelta(hours=1), timedelta(days=7)], ids=["an_hour_ago", "7_days_ahead"]
)
def test_plan_accepts_a_departure_on_the_window_edges(offset):
    assert valid(departure=(PLAN_NOW + offset).isoformat())


@pytest.mark.parametrize("load", [-1, 80_001])
def test_plan_rejects_a_load_outside_0_to_80000(load):
    response = post(trip(load_lb=load))
    assert response.status_code == 400
    assert "load_lb" in response.json()["fields"]


@pytest.mark.parametrize("load", [0, 80_000])
def test_plan_accepts_a_load_on_the_edges(load):
    assert valid(load_lb=load)


def test_plan_rejects_an_interval_that_is_not_offered():
    assert "interval_mi" in post(trip(interval_mi=30)).json()["fields"]


# A mile of latitude, in degrees, on the haversine earth the check uses.
MILE_DEG = 1 / 3958.8 * 180 / math.pi


def test_plan_accepts_places_just_over_a_mile_apart():
    nearby = Point(DENVER.lat + 1.01 * MILE_DEG, DENVER.lon)
    assert valid(destination=place("Nearby", nearby))


def test_plan_rejects_places_just_under_a_mile_apart():
    nearby = Point(DENVER.lat + 0.99 * MILE_DEG, DENVER.lon)
    assert not valid(destination=place("Nearby", nearby))


@pytest.mark.parametrize(("lat", "lon"), [(90, 0), (-90, 0), (0, 180), (0, -180)])
def test_plan_accepts_coordinates_on_their_limits(lat, lon):
    assert valid(destination={"label": "Edge", "lat": lat, "lon": lon})


@pytest.mark.parametrize(("lat", "lon"), [(90.01, 0), (-90.01, 0), (0, 180.01), (0, -180.01)])
def test_plan_rejects_coordinates_past_their_limits(lat, lon):
    assert not valid(destination={"label": "Edge", "lat": lat, "lon": lon})


def test_plan_rejects_the_same_place_twice():
    response = post(trip(destination=place("Denver", DENVER)))
    assert response.status_code == 400
    assert response.json()["detail"] == "Origin and destination must be at least a mile apart."


# --- Failures (plan-api D5) ----------------------------------------------------------------------


def test_plan_no_route_error(monkeypatch):
    recorded(monkeypatch, "stadia_route_no_path")
    response = post(trip(destination=place("Backcountry", BACKCOUNTRY)))
    assert response.status_code == 422
    assert set(response.json()) == {"detail"}


def test_plan_provider_failure_error(monkeypatch):
    recorded(monkeypatch)

    class Down:
        def hourly(self, *args):
            raise ProviderError("The weather provider could not be reached.")

    monkeypatch.setattr(open_meteo, "default", Down)
    response = post(trip())
    assert response.status_code == 502
    assert response.json() == {"detail": "The weather provider could not be reached."}


def test_an_oversized_body_keeps_the_error_shape():
    response = Client().post(
        "/api/plan", '{"x": "' + "a" * 3_000_000 + '"}', content_type="application/json"
    )
    assert response.status_code == 400
    assert set(response.json()) == {"detail"}
