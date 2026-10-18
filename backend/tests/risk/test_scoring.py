import math
import random

import pytest

from risk.levels import Level
from risk.scoring import CheckpointLevel, owned_miles, summarize_route

L, M, H, S, N = Level.LOW, Level.MODERATE, Level.HIGH, Level.SEVERE, Level.NO_TRAVEL


# recommendation D1: each checkpoint owns the stretch centred on it.
def test_owned_miles_centre_on_each_checkpoint():
    # Checkpoints every 25 mi on a 60 mi route, plus the destination.
    assert owned_miles([0, 25, 50, 60], route_miles=60) == [12.5, 25, 17.5, 5]


def test_first_and_last_checkpoints_reach_the_route_ends():
    assert owned_miles([5, 15], route_miles=20) == [10, 10]


def test_single_checkpoint_owns_the_whole_route():
    assert owned_miles([0], route_miles=8) == [8]


def test_owned_miles_sum_to_the_route_length():
    rng = random.Random(20261018)
    for _ in range(500):
        route_miles = rng.uniform(1, 3000)
        miles = sorted(rng.uniform(0, route_miles) for _ in range(rng.randint(1, 120)))
        assert math.isclose(sum(owned_miles(miles, route_miles)), route_miles)


@pytest.mark.parametrize(
    ("miles", "route_miles", "problem"),
    [
        ([], 10, "at least one checkpoint"),
        ([0, 5], 0, "route length must be positive"),
        ([5, 2], 10, "in order along the route"),
        ([0, 11], 10, "within the route"),
        ([-1, 5], 10, "within the route"),
    ],
)
def test_owned_miles_rejects_inconsistent_input(miles, route_miles, problem):
    with pytest.raises(ValueError, match=problem):
        owned_miles(miles, route_miles)


# recommendation D2: miles at level and mean level are weighted by owned miles.
def test_mean_level_is_weighted_by_owned_miles():
    summary = summarize_route(
        route_id="a",
        distance_miles=50,
        duration_s=3600,
        checkpoints=[CheckpointLevel(0, L), CheckpointLevel(25, S), CheckpointLevel(50, L)],
    )

    # Owned miles are 12.5, 25 and 12.5, so Severe covers half the route.
    assert summary.miles_at(S) == 25
    assert summary.miles_at(L) == 25
    assert summary.miles_at(N) == 0
    assert summary.mean_level == 1.5


def test_miles_at_every_level_sum_to_the_distance():
    summary = summarize_route(
        route_id="a",
        distance_miles=60,
        duration_s=4000,
        checkpoints=[
            CheckpointLevel(0, M),
            CheckpointLevel(25, H),
            CheckpointLevel(50, N),
            CheckpointLevel(60, L),
        ],
    )

    assert sum(summary.miles_at(level) for level in Level) == 60
