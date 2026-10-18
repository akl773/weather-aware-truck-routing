import math

import pytest

from providers.geo import (
    EARTH_RADIUS_MI,
    Point,
    cumulative_mi,
    decode_polyline,
    haversine_mi,
    interpolate,
    offset_point,
    overlap_share,
    resample,
)

CHICAGO = Point(41.8781, -87.6298)
DENVER = Point(39.7392, -104.9903)


def test_haversine_chicago_to_denver_is_about_920_miles():
    assert haversine_mi(CHICAGO, DENVER) == pytest.approx(920, abs=3)


def test_decode_polyline6_matches_the_reference_encoding():
    # Valhalla's documented example, precision 6.
    assert decode_polyline("_izlhA~rlgdF_{geC~ywl@_kwzCn`{nI") == [
        Point(38.5, -120.2),
        Point(40.7, -120.95),
        Point(43.252, -126.453),
    ]


def test_decode_empty_polyline_is_empty():
    assert decode_polyline("") == []


def straight_line(miles: float, step: float = 5.0) -> list[Point]:
    """A due-east line from (40, -100); one degree of longitude there is ~52.9 miles."""
    mi_per_deg = 69.0 * math.cos(math.radians(40))
    count = int(miles / step)
    return [Point(40.0, -100.0 + k * step / mi_per_deg) for k in range(count + 1)]


def test_interpolate_halfway_between_two_points():
    points = [Point(0, 0), Point(0, 2)]
    assert interpolate(points, [0.0, 10.0], 5.0) == Point(0, 1)


def test_interpolate_clamps_to_the_ends():
    points = [Point(0, 0), Point(0, 2)]
    assert interpolate(points, [0.0, 10.0], -1) == Point(0, 0)
    assert interpolate(points, [0.0, 10.0], 11) == Point(0, 2)


def test_resample_keeps_the_last_point():
    line = straight_line(10)
    samples = resample(line, cumulative_mi(line), 3.0)
    assert len(samples) == 5  # 0, 3, 6, 9 and the end at 10
    assert samples[-1] == line[-1]


def test_overlap_of_a_route_with_itself_is_total():
    line = straight_line(100)
    assert overlap_share(line, line) == 1.0


def test_overlap_sees_shared_road_between_sparse_shape_points():
    # Same road, but one copy has a shape point only every 20 miles.
    dense = straight_line(100, step=1)
    sparse = straight_line(100, step=20)
    assert overlap_share(dense, sparse) == 1.0


def test_overlap_of_parallel_roads_10_miles_apart_is_zero():
    line = straight_line(100)
    parallel = [Point(p.lat + 10 / 69.0, p.lon) for p in line]
    assert overlap_share(line, parallel) == 0.0


@pytest.mark.parametrize(("apart_mi", "share"), [(0.29, 1.0), (0.31, 0.0)])
def test_roads_within_0_3_miles_count_as_the_same_road(apart_mi, share):
    line = straight_line(20, step=0.5)
    deg = apart_mi / (EARTH_RADIUS_MI * math.pi / 180)
    parallel = [Point(p.lat + deg, p.lon) for p in line]
    assert haversine_mi(line[0], parallel[0]) == pytest.approx(apart_mi)
    assert overlap_share(line, parallel) == share


def test_overlap_counts_only_the_shared_stretch():
    line = straight_line(100, step=1)
    # Shares the first 50 miles, then bends 10 miles north.
    half = [p if i <= 50 else Point(p.lat + 10 / 69.0, p.lon) for i, p in enumerate(line)]
    # The bend itself adds about 10 miles, so 50 shared miles are under half of the route.
    assert overlap_share(half, line) == pytest.approx(50 / cumulative_mi(half)[-1], abs=0.02)


def test_offset_point_goes_left_of_travel_for_positive_offsets():
    origin, destination = Point(40, -100), Point(40, -90)  # due east
    left = offset_point(Point(40, -95), origin, destination, 50)
    right = offset_point(Point(40, -95), origin, destination, -50)
    assert left.lat > 40 > right.lat
    assert haversine_mi(Point(40, -95), left) == pytest.approx(50, rel=0.01)


def test_offset_point_rejects_identical_ends():
    with pytest.raises(ValueError, match="same point"):
        offset_point(CHICAGO, CHICAGO, CHICAGO, 10)
