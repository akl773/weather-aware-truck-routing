from datetime import timedelta

import pytest

import trips.plan
from providers.geo import Point, cumulative_mi, resample
from providers.open_meteo import BASE_URL as WEATHER_URL
from providers.open_meteo import OpenMeteo, Series, snap
from providers.routing import Route, plan_routes
from providers.stadia import BASE_URL as ROUTING_URL
from providers.stadia import StadiaMaps
from risk.levels import Level
from tests.providers.replay import replay_client
from tests.providers.scenarios import (
    CORRIDOR_PATH,
    CORRIDOR_WEATHER_FIXTURE,
    DENVER,
    LOAD_LB,
    PLAN_DEPARTURE,
    PLAN_NOW,
    SALT_LAKE_CITY,
)
from trips.corridor import (
    CELL_SIZES_DEG,
    CorridorTooLarge,
    corridor_cells,
    corridor_frames,
)
from trips.plan import classify_checkpoint, readings_at

# Miles per degree of latitude on the haversine earth the corridor test uses.
MI_PER_DEG = 3958.8 * 3.141592653589793 / 180


@pytest.fixture(scope="module")
def salt_lake_paths():
    router = StadiaMaps(replay_client("stadia_route_denver_salt_lake_city", ROUTING_URL), "k")
    return [route.points for route in plan_routes(router, DENVER, SALT_LAKE_CITY, LOAD_LB)]


def containing_cell(point: Point, size: float) -> Point:
    return Point(round(round(point.lat / size) * size, 4), round(round(point.lon / size) * size, 4))


# --- Cells (D1) ----------------------------------------------------------------------------------


@pytest.mark.parametrize("max_cells", [250, 60, 40])
def test_cells_cover_every_route_point(salt_lake_paths, max_cells):
    corridor = corridor_cells(salt_lake_paths, max_cells)
    cells = set(corridor.cells)
    for path in salt_lake_paths:
        for point in resample(path, cumulative_mi(path), 0.5):
            assert containing_cell(point, corridor.cell_deg) in cells


def east_west_path(lat: float) -> list[Point]:
    return [Point(lat, -100.0), Point(lat, -99.0)]


def test_a_cell_centre_24_9_miles_from_a_route_is_in_the_corridor():
    path = east_west_path(40.35 - 24.9 / MI_PER_DEG)
    assert Point(40.35, -99.45) in corridor_cells([path]).cells


def test_a_cell_centre_25_1_miles_from_a_route_is_not():
    path = east_west_path(40.35 - 25.1 / MI_PER_DEG)
    assert Point(40.35, -99.45) not in corridor_cells([path]).cells


def test_cell_size_grows_until_the_corridor_fits(salt_lake_paths):
    corridor = corridor_cells(salt_lake_paths)
    assert corridor.cell_deg == 0.3  # these recorded routes need 752 cells at 0.15°
    fits = len(corridor.cells)
    assert corridor_cells(salt_lake_paths, fits).cell_deg == 0.3
    assert corridor_cells(salt_lake_paths, fits - 1).cell_deg > 0.3


def test_cell_centres_sit_on_the_weather_lattice(salt_lake_paths):
    # Lower the cap one cell at a time to walk every size on the ladder.
    sizes, cap = [], 10_000
    while True:
        try:
            corridor = corridor_cells(salt_lake_paths, cap)
        except CorridorTooLarge:
            break
        sizes.append(corridor.cell_deg)
        assert all(snap(cell) == cell for cell in corridor.cells)
        cap = len(corridor.cells) - 1
    assert sizes == list(CELL_SIZES_DEG)


def test_cells_near_the_180th_meridian_wrap_into_range():
    corridor = corridor_cells([[Point(65.0, 179.9), Point(65.0, 179.99)]])
    assert all(-180 <= cell.lon < 180 for cell in corridor.cells)
    assert any(cell.lon < 0 for cell in corridor.cells)
    assert len(set(corridor.cells)) == len(corridor.cells)


def test_no_cell_lies_past_a_pole():
    corridor = corridor_cells([[Point(89.9, 0.0), Point(89.9, 10.0)]])
    assert all(-90 <= cell.lat <= 90 for cell in corridor.cells)


def test_a_corridor_too_large_at_the_coarsest_size_is_refused(salt_lake_paths):
    with pytest.raises(CorridorTooLarge):
        corridor_cells(salt_lake_paths, max_cells=5)


# --- Frames (D2) ---------------------------------------------------------------------------------


@pytest.fixture
def recorded_weather():
    return OpenMeteo(replay_client(CORRIDOR_WEATHER_FIXTURE, WEATHER_URL))


@pytest.fixture
def recorded_frames(recorded_weather):
    corridor = corridor_cells([CORRIDOR_PATH])
    frames = corridor_frames(
        corridor,
        departure=PLAN_DEPARTURE,
        load_lb=LOAD_LB,
        weather=recorded_weather,
        now=PLAN_NOW,
    )
    return corridor, frames


def test_frames_run_from_departure_to_48_hours(recorded_frames):
    corridor, frames = recorded_frames
    assert [f.hour for f in frames] == list(range(49))
    assert all(len(f.levels) == len(f.readings) == len(corridor.cells) for f in frames)


def test_cell_readings_follow_the_checkpoint_rules(recorded_frames, recorded_weather):
    corridor, frames = recorded_frames
    series = recorded_weather.hourly(corridor.cells, PLAN_DEPARTURE - timedelta(hours=1), 72)
    for frame in frames[::6]:
        eta = PLAN_DEPARTURE + timedelta(hours=frame.hour)
        for i, cell in enumerate(corridor.cells):
            readings = readings_at(series[cell], eta)
            assert frame.readings[i] == readings
            assert frame.levels[i] == classify_checkpoint(readings, LOAD_LB)[0]


class SteadyWind:
    """46 mph everywhere, all the time: Severe, or No Travel above 30,000 lb."""

    def hourly(self, points, start, hours):
        times = tuple(start.timestamp() + 3600 * k for k in range(hours))
        calm = (0.0,) * hours
        return {p: Series(times, (46.0,) * hours, (46.0,) * hours, calm, calm) for p in points}


@pytest.mark.parametrize(("load_lb", "level"), [(30_000, Level.SEVERE), (30_001, Level.NO_TRAVEL)])
def test_frame_levels_apply_the_load_rules(load_lb, level):
    frames = corridor_frames(
        corridor_cells([CORRIDOR_PATH]),
        departure=PLAN_DEPARTURE,
        load_lb=load_lb,
        weather=SteadyWind(),
        now=PLAN_NOW,
    )
    assert {lvl for frame in frames for lvl in frame.levels} == {level}


class OneGap:
    """Calm everywhere, except no rain forecast in hour 2 of the window."""

    def hourly(self, points, start, hours):
        times = tuple(start.timestamp() + 3600 * k for k in range(hours))
        calm = (0.0,) * hours
        rain = tuple(None if k == 2 else 0.0 for k in range(hours))
        return {p: Series(times, calm, calm, rain, calm) for p in points}


def test_a_cell_without_a_full_forecast_is_unknown():
    # The window starts an hour before departure (11:00). Rain sample 2 is valid at 12:30, so
    # every time from 11:30 to 13:30 interpolates with it: frames at 12:00 and 13:00.
    frames = corridor_frames(
        corridor_cells([CORRIDOR_PATH]),
        departure=PLAN_DEPARTURE,
        load_lb=LOAD_LB,
        weather=OneGap(),
        now=PLAN_NOW,
    )
    assert set(frames[0].levels) == set(frames[1].levels) == {None}
    assert {r.rain_in_hr for r in frames[1].readings} == {None}
    assert {r.wind_mph for r in frames[1].readings} == {0.0}
    assert set(frames[2].levels) == {Level.LOW}


def straight_route_from(start: Point) -> Route:
    points = tuple(Point(start.lat + 0.5 * i / 50, start.lon) for i in range(51))
    cum_mi = tuple(cumulative_mi(points))
    return Route(points, cum_mi, tuple(m * 60 for m in cum_mi))


class Warming:
    """Wind rising 3 mph an hour from 20 mph at the plan's departure, so the hour matters."""

    def hourly(self, points, start, hours):
        times = tuple(start.timestamp() + 3600 * k for k in range(hours))
        wind = tuple(20.0 + 3 * (t - PLAN_DEPARTURE.timestamp()) / 3600 for t in times)
        calm = (0.0,) * hours
        return {p: Series(times, wind, wind, calm, calm) for p in points}


@pytest.mark.parametrize("hour", [0, 5, 7])
def test_a_cell_matches_a_plan_checkpoint_at_its_centre(monkeypatch, hour):
    corridor = corridor_cells([CORRIDOR_PATH])
    cell = corridor.cells[len(corridor.cells) // 2]
    departure = PLAN_DEPARTURE + timedelta(hours=hour)
    monkeypatch.setattr(trips.plan, "plan_routes", lambda *args: [straight_route_from(cell)])
    plan = trips.plan.plan_trip(
        origin=cell,
        destination=Point(cell.lat + 0.5, cell.lon),
        departure=departure,
        load_lb=LOAD_LB,
        interval_mi=25,
        router=None,
        weather=Warming(),
        now=PLAN_NOW,
    )
    checkpoint = plan.routes[0].checkpoints[0]
    frame = corridor_frames(
        corridor, departure=PLAN_DEPARTURE, load_lb=LOAD_LB, weather=Warming(), now=PLAN_NOW
    )[hour]
    i = corridor.cells.index(cell)
    assert checkpoint.eta == departure
    assert frame.readings[i] == checkpoint.readings
    assert frame.levels[i] == checkpoint.level


class ThresholdRain:
    def hourly(self, points, start, hours):
        times = tuple(start.timestamp() + 3600 * k for k in range(hours))
        calm = (0.0,) * hours
        rain = (1.004,) * hours
        return {p: Series(times, calm, calm, rain, calm) for p in points}


def test_no_travel_rain_stays_no_travel_when_corridor_response_rounds_to_one():
    from trips.serializers import corridor_response

    corridor = corridor_cells([CORRIDOR_PATH])
    frames = corridor_frames(
        corridor,
        departure=PLAN_DEPARTURE,
        load_lb=0,
        weather=ThresholdRain(),
        now=PLAN_NOW,
    )
    response = corridor_response(corridor, frames, PLAN_DEPARTURE)
    assert all(r.rain_in_hr == 1.004 for f in frames for r in f.readings)
    assert all(level == 4 for f in response["frames"] for level in f["level"])
    assert all(rain == 1.0 for f in response["frames"] for rain in f["rain_in_hr"])


def test_no_travel_rain_drives_route_summary_before_response_rounding():
    from tests.trips.test_plan import recorded_router
    from trips.serializers import plan_response

    plan = trips.plan.plan_trip(
        origin=DENVER,
        destination=SALT_LAKE_CITY,
        departure=PLAN_DEPARTURE,
        load_lb=LOAD_LB,
        interval_mi=25,
        router=recorded_router(),
        weather=ThresholdRain(),
        now=PLAN_NOW,
    )
    response = plan_response(plan)
    for route in plan.routes:
        assert route.summary.miles_at(Level.NO_TRAVEL) == pytest.approx(
            route.summary.distance_miles
        )
    for route in response["routes"]:
        assert all(
            c["level"] == 4 and c["readings"]["rain_in_hr"] == 1.0 for c in route["checkpoints"]
        )
    assert response["recommendation"]["all_routes_cross_no_travel"] is True
