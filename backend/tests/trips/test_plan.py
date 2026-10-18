from datetime import UTC, datetime
from itertools import pairwise

import pytest

from providers.open_meteo import BASE_URL as WEATHER_URL
from providers.open_meteo import OpenMeteo, Series
from providers.stadia import BASE_URL as ROUTING_URL
from providers.stadia import StadiaMaps
from risk.classification import Condition
from risk.levels import Level
from tests.providers.replay import replay_client
from tests.providers.scenarios import (
    DENVER,
    LOAD_LB,
    PLAN_DEPARTURE,
    PLAN_INTERVAL_MI,
    PLAN_NOW,
    PLAN_WEATHER_FIXTURE,
    SALT_LAKE_CITY,
)
from trips.plan import Readings, classify_checkpoint, plan_trip, readings_at

T0 = datetime(2026, 10, 19, 12, 0, tzinfo=UTC).timestamp()


def series(**values) -> Series:
    base = {
        "times": (T0, T0 + 3600),
        "wind_mph": (10.0, 20.0),
        "gust_mph": (30.0, 30.0),
        "rain_in_hr": (0.0, 0.0),
        "snow_in_hr": (0.0, 0.0),
    }
    return Series(**(base | values))


def at(seconds: float) -> datetime:
    return datetime.fromtimestamp(T0 + seconds, UTC)


# --- Readings (plan-api D2) ----------------------------------------------------------------------


def test_readings_interpolate_at_the_eta():
    assert readings_at(series(), at(1800)).wind_mph == 15.0


def test_hourly_totals_are_read_at_their_mid_hour():
    # Totals at T0 and T0+1h are valid at T0-30min and T0+30min; at T0 we are halfway.
    readings = readings_at(series(rain_in_hr=(0.1, 0.3)), at(0))
    assert readings.rain_in_hr == 0.2


def test_readings_are_rounded_as_shown():
    readings = readings_at(series(wind_mph=(44.94, 44.96), rain_in_hr=(0.2449, 0.2451)), at(1800))
    assert readings.wind_mph == 45.0
    assert readings.rain_in_hr == 0.25


def test_level_matches_the_reading_shown():
    # Raw 1.004 in/hr would be No Travel (> 1.00); shown as 1.00 it is Severe, and so is the level.
    readings = readings_at(series(rain_in_hr=(1.004, 1.004)), at(1800))
    level, drivers, _ = classify_checkpoint(readings, LOAD_LB)
    assert readings.rain_in_hr == 1.0
    assert level is Level.SEVERE
    assert drivers == (Condition.RAIN,)


def test_readings_outside_the_forecast_are_unknown():
    readings = readings_at(series(), at(-7200))
    assert readings == Readings(None, None, None, None)


# --- Unknown (plan-api D3) -----------------------------------------------------------------------


def test_missing_rain_makes_the_level_unknown():
    assert classify_checkpoint(Readings(10.0, 12.0, None, 0.0), LOAD_LB) == (None, (), False)


def test_missing_gust_only_clears_the_gust_flag():
    level, drivers, gusty = classify_checkpoint(Readings(46.0, None, 0.0, 0.0), 40_000)
    assert level is Level.NO_TRAVEL  # 45-54 mph with more than 30,000 lb
    assert drivers == (Condition.WIND,)
    assert gusty is False


def test_load_rules_apply_through_the_plan():
    assert classify_checkpoint(Readings(46.0, 46.0, 0.0, 0.0), 30_000)[0] is Level.SEVERE
    assert classify_checkpoint(Readings(46.0, 46.0, 0.0, 0.0), 30_001)[0] is Level.NO_TRAVEL


# --- A recorded plan -----------------------------------------------------------------------------


@pytest.fixture
def recorded_plan():
    return plan_trip(
        origin=DENVER,
        destination=SALT_LAKE_CITY,
        departure=PLAN_DEPARTURE,
        load_lb=LOAD_LB,
        interval_mi=PLAN_INTERVAL_MI,
        router=StadiaMaps(replay_client("stadia_route_denver_salt_lake_city", ROUTING_URL), "k"),
        weather=OpenMeteo(replay_client(PLAN_WEATHER_FIXTURE, WEATHER_URL)),
        now=PLAN_NOW,
    )


def test_plan_has_three_routes_with_ids_in_provider_order(recorded_plan):
    assert [r.id for r in recorded_plan.routes] == ["A", "B", "C"]


def test_every_checkpoint_has_a_known_level_inside_the_forecast(recorded_plan):
    for route in recorded_plan.routes:
        assert all(c.level is not None for c in route.checkpoints)
        assert route.summary.unknown_miles == 0


def test_owned_stretches_tile_each_route(recorded_plan):
    for route in recorded_plan.routes:
        cps = route.checkpoints
        assert cps[0].owned_from_mi == 0
        assert cps[-1].owned_to_mi == pytest.approx(route.summary.distance_miles)
        assert all(a.owned_to_mi == b.owned_from_mi for a, b in pairwise(cps))


def test_simplified_path_keeps_the_ends_and_miles(recorded_plan):
    for route in recorded_plan.routes:
        first, last = route.path[0], route.path[-1]
        assert first[2] == 0
        assert last[2] == pytest.approx(route.summary.distance_miles, abs=0.01)
        assert len(route.path) < 1000
        assert all(b[2] >= a[2] for a, b in pairwise(route.path))


def test_weather_window_covers_the_heatmap(recorded_plan):
    assert recorded_plan.weather_start == datetime(2026, 10, 19, 11, 0, tzinfo=UTC)
    assert recorded_plan.weather_hours == 72


def test_recommendation_is_one_of_the_routes(recorded_plan):
    assert recorded_plan.recommendation.recommended.route_id in {"A", "B", "C"}
    assert recorded_plan.recommendation.reason
