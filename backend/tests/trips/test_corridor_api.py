import pytest
from django.core.cache import cache
from django.test import Client
from django.utils import timezone

from providers import open_meteo
from providers.errors import ProviderError
from tests.providers.replay import replay_client
from tests.providers.scenarios import (
    CORRIDOR_PATH,
    CORRIDOR_WEATHER_FIXTURE,
    LOAD_LB,
    PLAN_DEPARTURE,
    PLAN_NOW,
)
from trips.serializers import MAX_PATH_POINTS, CorridorRequestSerializer

PATH = [[p.lon, p.lat] for p in CORRIDOR_PATH]


@pytest.fixture(autouse=True)
def frozen(monkeypatch):
    cache.clear()
    monkeypatch.setattr(timezone, "now", lambda: PLAN_NOW)
    yield
    cache.clear()


@pytest.fixture
def recorded(monkeypatch):
    weather = open_meteo.OpenMeteo(replay_client(CORRIDOR_WEATHER_FIXTURE, open_meteo.BASE_URL))
    monkeypatch.setattr(open_meteo, "default", lambda: weather)


def request(**changes):
    body = {"paths": [PATH], "departure": PLAN_DEPARTURE.isoformat(), "load_lb": LOAD_LB}
    return body | changes


def post(body):
    return Client().post("/api/corridor", body, content_type="application/json")


def valid(**changes) -> bool:
    serializer = CorridorRequestSerializer(data=request(**changes), context={"now": PLAN_NOW})
    return serializer.is_valid()


# --- Response (D4) -------------------------------------------------------------------------------


def test_corridor_returns_a_level_per_cell_per_frame(recorded):
    body = post(request()).json()
    cells = len(body["cells"])
    assert body["cell_deg"] == 0.15
    assert body["start"] == "2026-10-19T12:00:00Z"
    assert [f["hour"] for f in body["frames"]] == list(range(49))
    for frame in body["frames"]:
        for name in ("level", "wind_mph", "gust_mph", "rain_in_hr", "snow_in_hr"):
            assert len(frame[name]) == cells
        assert all(level in range(5) for level in frame["level"])


def test_corridor_numbers_are_the_numbers_shown(recorded):
    places = {"wind_mph": 1, "gust_mph": 1, "rain_in_hr": 2, "snow_in_hr": 2}
    for frame in post(request()).json()["frames"]:
        for name, digits in places.items():
            assert all(v is None or v == round(v, digits) for v in frame[name])


def test_corridor_accepts_a_plan_path_with_miles(recorded):
    with_miles = [[*PATH[0], 0.0], [*PATH[1], 21.4]]
    assert post(request(paths=[with_miles])).json() == post(request()).json()


# --- Input (D3) ----------------------------------------------------------------------------------


def test_corridor_accepts_three_paths():
    assert valid(paths=[PATH] * 3)


@pytest.mark.parametrize("paths", [[], [PATH] * 4], ids=["none", "four"])
def test_corridor_rejects_a_path_count_outside_1_to_3(paths):
    response = post(request(paths=paths))
    assert response.status_code == 400
    assert "paths" in response.json()["fields"]


def test_corridor_accepts_a_path_of_the_most_points():
    assert valid(paths=[[[-105.0, 39.7 + i * 1e-5] for i in range(MAX_PATH_POINTS)]])


@pytest.mark.parametrize(
    "path",
    [
        [[-105.0, 39.7]],
        [[-105.0, 39.7 + i * 1e-5] for i in range(MAX_PATH_POINTS + 1)],
        "not a path",
        [[-105.0], [-105.1, 39.8]],
        [[-105.0, 39.7, 0.0, 1.0], [-105.1, 39.8]],
        [["-105", "39.7"], [-105.1, 39.8]],
        [[True, 39.7], [-105.1, 39.8]],
        [None, [-105.1, 39.8]],
    ],
    ids=[
        "one_point",
        "too_many_points",
        "not_a_list",
        "one_coordinate",
        "four_numbers",
        "strings",
        "boolean",
        "null_point",
    ],
)
def test_corridor_rejects_a_malformed_path(path):
    response = post(request(paths=[path]))
    assert response.status_code == 400
    assert "paths" in response.json()["fields"]


@pytest.mark.parametrize(("lon", "lat"), [(180, 0), (-180, 0), (0, 90), (0, -90)])
def test_corridor_accepts_coordinates_on_their_limits(lon, lat):
    assert valid(paths=[[[lon, lat], [0, 0]]])


@pytest.mark.parametrize(("lon", "lat"), [(180.01, 0), (-180.01, 0), (0, 90.01), (0, -90.01)])
def test_corridor_rejects_coordinates_past_their_limits(lon, lat):
    assert not valid(paths=[[[lon, lat], [0, 0]]])


def test_corridor_rejects_a_departure_without_an_offset():
    assert "departure" in post(request(departure="2026-10-19T12:00:00")).json()["fields"]


def test_corridor_rejects_a_load_over_80000():
    assert "load_lb" in post(request(load_lb=80_001)).json()["fields"]


def test_corridor_rejects_routes_that_cover_too_much_ground():
    # Sweeping the continent row by row: no cell size on the ladder fits it in 250 cells.
    sweep = [[-125.0 if row % 2 else -67.0, 25.0 + row] for row in range(25)]
    response = post(request(paths=[sweep]))
    assert response.status_code == 400
    assert "too much ground" in response.json()["fields"]["paths"][0]


def test_corridor_provider_failure_error(monkeypatch):
    class Down:
        def hourly(self, *args):
            raise ProviderError("The weather provider could not be reached.")

    monkeypatch.setattr(open_meteo, "default", Down)
    response = post(request())
    assert response.status_code == 502
    assert response.json() == {"detail": "The weather provider could not be reached."}
