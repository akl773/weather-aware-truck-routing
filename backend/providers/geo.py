"""Geometry on latitude/longitude points: distances, polyline decoding, resampling and overlap.

Pure functions. Distances are great-circle miles, which is accurate to well under 1% at the scales a
truck route covers.
"""

import bisect
import itertools
import math
from collections.abc import Sequence
from typing import NamedTuple

EARTH_RADIUS_MI = 3958.8


class Point(NamedTuple):
    lat: float
    lon: float


def haversine_mi(a: Point, b: Point) -> float:
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = lat2 - lat1
    dlon = math.radians(b.lon - a.lon)
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_MI * math.asin(min(1.0, math.sqrt(h)))


def decode_polyline(encoded: str, precision: int = 6) -> list[Point]:
    """Decode a Google-format encoded polyline. Valhalla uses precision 6."""
    factor = 10**precision
    points: list[Point] = []
    index = lat = lon = 0
    while index < len(encoded):
        deltas = []
        for _ in range(2):
            shift = result = 0
            while True:
                byte = ord(encoded[index]) - 63
                index += 1
                result |= (byte & 0x1F) << shift
                shift += 5
                if byte < 0x20:
                    break
            deltas.append(~(result >> 1) if result & 1 else result >> 1)
        lat += deltas[0]
        lon += deltas[1]
        points.append(Point(lat / factor, lon / factor))
    return points


def interpolate(points: Sequence[Point], cum_mi: Sequence[float], mile: float) -> Point:
    """The point `mile` miles along a polyline whose cumulative distances are `cum_mi`."""
    if mile <= cum_mi[0]:
        return points[0]
    if mile >= cum_mi[-1]:
        return points[-1]
    i = bisect.bisect_right(cum_mi, mile)
    start, end = cum_mi[i - 1], cum_mi[i]
    t = (mile - start) / (end - start) if end > start else 0.0
    a, b = points[i - 1], points[i]
    return Point(a.lat + (b.lat - a.lat) * t, a.lon + (b.lon - a.lon) * t)


def resample(points: Sequence[Point], cum_mi: Sequence[float], step_mi: float) -> list[Point]:
    """Points every `step_mi` along the polyline, plus its last point."""
    count = int(cum_mi[-1] // step_mi)
    samples = [interpolate(points, cum_mi, k * step_mi) for k in range(count + 1)]
    if cum_mi[-1] - count * step_mi > 1e-9:
        samples.append(points[-1])
    return samples


def cumulative_mi(points: Sequence[Point]) -> list[float]:
    cum = [0.0]
    for a, b in itertools.pairwise(points):
        cum.append(cum[-1] + haversine_mi(a, b))
    return cum


OVERLAP_STEP_MI = 0.25
OVERLAP_TOLERANCE_MI = 0.3


def overlap_share(route: Sequence[Point], other: Sequence[Point]) -> float:
    """Share of `route`'s length that runs on `other` (routing D5).

    Both are resampled every 0.25 mile first, because Valhalla leaves miles between shape points on
    straight roads and raw points would miss shared road.
    """
    samples = resample(route, cumulative_mi(route), OVERLAP_STEP_MI)
    others = resample(other, cumulative_mi(other), OVERLAP_STEP_MI)
    # Bucket the other route's samples on a grid about as wide as the tolerance, so each lookup
    # checks the 3x3 neighbourhood instead of every sample.
    cell_deg = OVERLAP_TOLERANCE_MI / 69.0
    grid: dict[tuple[int, int], list[Point]] = {}
    for p in others:
        grid.setdefault((int(p.lat // cell_deg), int(p.lon // cell_deg)), []).append(p)

    def near(p: Point) -> bool:
        row, col = int(p.lat // cell_deg), int(p.lon // cell_deg)
        # Longitude degrees shrink with latitude, so widen the column search to keep the radius.
        span = max(1, math.ceil(1 / max(math.cos(math.radians(p.lat)), 0.1)))
        return any(
            haversine_mi(p, q) <= OVERLAP_TOLERANCE_MI
            for dr in (-1, 0, 1)
            for dc in range(-span, span + 1)
            for q in grid.get((row + dr, col + dc), ())
        )

    return sum(near(p) for p in samples) / len(samples)


def offset_point(anchor: Point, origin: Point, destination: Point, offset_mi: float) -> Point:
    """`anchor` moved `offset_mi` perpendicular to the origin-destination line (routing D4).

    Positive offsets go left of the direction of travel, negative ones right. A local flat-earth
    approximation is accurate enough for placing a via point the router then snaps to a road.
    """
    mi_per_deg_lat = 69.0
    mi_per_deg_lon = 69.0 * math.cos(math.radians(anchor.lat))
    dx = (destination.lon - origin.lon) * mi_per_deg_lon
    dy = (destination.lat - origin.lat) * mi_per_deg_lat
    length = math.hypot(dx, dy)
    if length == 0:
        raise ValueError("origin and destination are the same point")
    left_x, left_y = -dy / length, dx / length
    return Point(
        anchor.lat + left_y * offset_mi / mi_per_deg_lat,
        anchor.lon + left_x * offset_mi / mi_per_deg_lon,
    )
