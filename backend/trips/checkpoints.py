"""Checkpoint placement, ETAs and conditions at an ETA (checkpoints-and-eta D1 to D5).

Pure: no Django, no I/O, no clock. Times in, times out.
"""

import bisect
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from providers.geo import Point, interpolate
from providers.routing import Route

INTERVALS_MI = (10, 25, 50)
DEFAULT_INTERVAL_MI = 25
# A destination this close to the last interval multiple replaces it (D1).
DESTINATION_SNAP_MI = 0.05


@dataclass(frozen=True)
class Checkpoint:
    mile: float
    point: Point
    eta: datetime


def checkpoint_miles(distance_mi: float, interval_mi: float) -> list[float]:
    """Mile 0, every interval after it, and the destination, strictly increasing (D1)."""
    if not distance_mi > 0:
        raise ValueError("route distance must be positive")
    if not interval_mi > 0:
        raise ValueError("interval must be positive")
    miles = [0.0]
    k = 1
    while k * interval_mi < distance_mi - DESTINATION_SNAP_MI:
        miles.append(float(k * interval_mi))
        k += 1
    miles.append(distance_mi)
    return miles


def seconds_at_mile(route: Route, mile: float) -> float:
    """Driving time to `mile`, linear between the shape points around it (D3)."""
    if mile <= 0:
        return 0.0
    if mile >= route.distance_mi:
        return route.duration_s
    i = bisect.bisect_right(route.cum_mi, mile)
    start, end = route.cum_mi[i - 1], route.cum_mi[i]
    t = (mile - start) / (end - start) if end > start else 0.0
    return route.cum_s[i - 1] + (route.cum_s[i] - route.cum_s[i - 1]) * t


def place_checkpoints(route: Route, interval_mi: float, departure: datetime) -> list[Checkpoint]:
    if departure.tzinfo is None:
        raise ValueError("departure must be timezone-aware")
    return [
        Checkpoint(
            mile=mile,
            point=interpolate(route.points, route.cum_mi, mile),
            eta=departure + timedelta(seconds=seconds_at_mile(route, mile)),
        )
        for mile in checkpoint_miles(route.distance_mi, interval_mi)
    ]


def value_at(times: Sequence[float], values: Sequence[float | None], t: float) -> float | None:
    """The value at time `t`, linear between the samples around it (D4); `None` if unknown (D5).

    `times` are increasing epoch seconds. Unknown means `t` is outside the samples or a bracketing
    sample is missing. Never 0, because 0 reads as calm.
    """
    if not times or t < times[0] or t > times[-1]:
        return None
    i = bisect.bisect_left(times, t)
    if times[i] == t:
        return values[i]
    before, after = values[i - 1], values[i]
    if before is None or after is None:
        return None
    share = (t - times[i - 1]) / (times[i] - times[i - 1])
    return before + (after - before) * share
