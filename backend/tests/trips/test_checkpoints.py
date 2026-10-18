import itertools
from datetime import UTC, datetime, timedelta

import pytest

from providers.geo import Point
from providers.routing import Route
from trips.checkpoints import (
    DEFAULT_INTERVAL_MI,
    INTERVALS_MI,
    checkpoint_miles,
    place_checkpoints,
    seconds_at_mile,
    value_at,
)

DEPARTURE = datetime(2026, 10, 20, 14, 0, tzinfo=UTC)


def two_pace_route() -> Route:
    """100 miles: the first 50 at 50 mph (1 h), the last 50 at 25 mph (2 h)."""
    points = (Point(40.0, -100.0), Point(40.0, -99.0), Point(40.0, -98.0))
    return Route(points, (0.0, 50.0, 100.0), (0.0, 3600.0, 3 * 3600.0))


# --- Placement (D1) ------------------------------------------------------------------------------


def test_checkpoints_on_an_exact_multiple():
    assert checkpoint_miles(100, 25) == [0, 25, 50, 75, 100]


def test_short_final_segment_ends_at_the_destination():
    assert checkpoint_miles(110, 25) == [0, 25, 50, 75, 100, 110]


def test_trip_shorter_than_one_interval():
    assert checkpoint_miles(18.5, 25) == [0, 18.5]


def test_destination_a_hair_past_a_multiple_replaces_it():
    # Float noise on the provider's length must not create a 0.0001-mile final stretch.
    assert checkpoint_miles(100.0001, 25) == [0, 25, 50, 75, 100.0001]


def test_destination_just_beyond_the_snap_distance_keeps_both():
    assert checkpoint_miles(100.06, 25) == [0, 25, 50, 75, 100, 100.06]


@pytest.mark.parametrize("interval", INTERVALS_MI)
@pytest.mark.parametrize("distance", [0.3, 9.99, 24.9, 50, 333.3, 2855.4])
def test_checkpoints_are_strictly_increasing_and_span_the_route(interval, distance):
    miles = checkpoint_miles(distance, interval)
    assert miles[0] == 0
    assert miles[-1] == distance
    assert all(b > a for a, b in itertools.pairwise(miles))
    assert all(b - a <= interval + 1e-9 for a, b in itertools.pairwise(miles))


def test_default_interval_is_25_miles():
    assert DEFAULT_INTERVAL_MI == 25


@pytest.mark.parametrize(("distance", "interval"), [(0, 25), (-5, 25), (100, 0)])
def test_placement_rejects_impossible_input(distance, interval):
    with pytest.raises(ValueError, match="positive"):
        checkpoint_miles(distance, interval)


# --- ETA (D3) ------------------------------------------------------------------------------------


def test_eta_follows_the_route_pace_not_an_average():
    route = two_pace_route()
    # 75 miles: 1 h for the fast half, then 25 miles at 25 mph = 1 h more.
    assert seconds_at_mile(route, 75) == 2 * 3600
    # An average pace (100 mi in 3 h) would say 2 h 15 min.


def test_eta_is_departure_plus_driving_time():
    checkpoints = place_checkpoints(two_pace_route(), 25, DEPARTURE)
    assert [c.eta - DEPARTURE for c in checkpoints] == [
        timedelta(0),
        timedelta(minutes=30),
        timedelta(hours=1),
        timedelta(hours=2),
        timedelta(hours=3),
    ]


def test_checkpoint_positions_lie_on_the_route():
    checkpoints = place_checkpoints(two_pace_route(), 25, DEPARTURE)
    assert checkpoints[1].point == pytest.approx(Point(40.0, -99.5))


def test_naive_departure_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        place_checkpoints(two_pace_route(), 25, datetime(2026, 10, 20, 14, 0))


# --- Conditions at the ETA (D4, D5) --------------------------------------------------------------

HOURS = [0.0, 3600.0, 7200.0]


def test_value_halfway_between_samples():
    assert value_at(HOURS, [10.0, 20.0, 40.0], 5400) == 30.0


def test_value_on_a_sample_is_that_sample():
    assert value_at(HOURS, [10.0, 20.0, 40.0], 3600) == 20.0


def test_value_outside_the_forecast_is_unknown():
    assert value_at(HOURS, [10.0, 20.0, 40.0], -1) is None
    assert value_at(HOURS, [10.0, 20.0, 40.0], 7201) is None
    assert value_at([], [], 0) is None


def test_missing_sample_is_unknown():
    assert value_at(HOURS, [10.0, None, 40.0], 1800) is None
    assert value_at(HOURS, [10.0, None, 40.0], 3600) is None


def test_zero_is_a_reading_not_a_gap():
    assert value_at(HOURS, [0.0, 0.0, 0.0], 1800) == 0.0
