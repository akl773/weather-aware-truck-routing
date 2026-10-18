from datetime import timedelta

import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from providers import open_meteo, stadia
from providers.errors import ProviderError
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


def test_response_numbers_are_the_numbers_shown(monkeypatch):
    recorded(monkeypatch)
    for route in post(trip()).json()["routes"]:
        summary = route["summary"]
        for miles in summary["miles_by_level"].values():
            assert miles == round(miles, 1)
        assert sum(summary["miles_by_level"].values()) == pytest.approx(
            summary["distance_mi"], abs=0.3
        )
        for checkpoint in route["checkpoints"]:
            r = checkpoint["readings"]
            assert r["wind_mph"] == round(r["wind_mph"], 1)
            assert r["rain_in_hr"] == round(r["rain_in_hr"], 2)


def test_an_offset_departure_is_read_as_the_same_instant(monkeypatch):
    recorded(monkeypatch)
    mountain = PLAN_DEPARTURE.astimezone(timezone.get_fixed_timezone(-360)).isoformat()
    assert post(trip(departure=mountain)).json() == post(trip()).json()


def test_interval_defaults_to_25_miles(monkeypatch):
    recorded(monkeypatch)
    body = trip()
    del body["interval_mi"]
    assert post(body).json()["routes"][0]["checkpoints"][1]["mile"] == 25.0


# --- Input (plan-api D1) -------------------------------------------------------------------------


def test_plan_rejects_a_departure_without_an_offset():
    response = post(trip(departure="2026-10-19T12:00:00"))
    assert response.status_code == 400
    assert "departure" in response.json()["fields"]


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
    body = trip(departure=(PLAN_NOW + offset).isoformat())
    assert PlanRequestSerializer(data=body, context={"now": PLAN_NOW}).is_valid()


@pytest.mark.parametrize("load", [-1, 80_001])
def test_plan_rejects_a_load_outside_0_to_80000(load):
    assert "load_lb" in post(trip(load_lb=load)).json()["fields"]


@pytest.mark.parametrize("load", [0, 80_000])
def test_plan_accepts_a_load_on_the_edges(load):
    body = trip(load_lb=load)
    assert PlanRequestSerializer(data=body, context={"now": PLAN_NOW}).is_valid()


def test_plan_rejects_an_interval_that_is_not_offered():
    assert "interval_mi" in post(trip(interval_mi=30)).json()["fields"]


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
