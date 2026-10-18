"""Owned miles and route summaries. See docs/decisions/recommendation.md."""

from collections.abc import Sequence
from dataclasses import dataclass
from itertools import pairwise

from risk.levels import Level


@dataclass(frozen=True)
class CheckpointLevel:
    mile: float  # distance from the origin along the route
    level: Level


def owned_miles(checkpoint_miles: Sequence[float], route_miles: float) -> list[float]:
    """Miles of road each checkpoint speaks for (D1).

    Boundaries sit halfway between neighbouring checkpoints; the first stretch starts at the origin
    and the last ends at the destination, so the result always sums to `route_miles`.
    """
    if not checkpoint_miles:
        raise ValueError("a route needs at least one checkpoint")
    if route_miles <= 0:
        raise ValueError("route length must be positive")
    if any(later < earlier for earlier, later in pairwise(checkpoint_miles)):
        raise ValueError("checkpoints must be in order along the route")
    if checkpoint_miles[0] < 0 or checkpoint_miles[-1] > route_miles:
        raise ValueError("checkpoints must lie within the route")

    midpoints = [(a + b) / 2 for a, b in pairwise(checkpoint_miles)]
    boundaries = [0.0, *midpoints, route_miles]
    return [end - start for start, end in pairwise(boundaries)]


@dataclass(frozen=True)
class RouteSummary:
    route_id: str
    distance_miles: float
    duration_s: float
    miles_by_level: tuple[float, ...]  # indexed by Level
    mean_level: float  # 0 (all Low) to 4 (all No Travel), weighted by owned miles

    def miles_at(self, level: Level) -> float:
        return self.miles_by_level[level]


def summarize_route(
    route_id: str,
    distance_miles: float,
    duration_s: float,
    checkpoints: Sequence[CheckpointLevel],
) -> RouteSummary:
    owned = owned_miles([checkpoint.mile for checkpoint in checkpoints], distance_miles)
    miles_by_level = [0.0] * len(Level)
    for checkpoint, miles in zip(checkpoints, owned, strict=True):
        miles_by_level[checkpoint.level] += miles
    # D2: weighted by owned miles, so the sampling interval does not change the mean.
    mean_level = sum(level * miles for level, miles in enumerate(miles_by_level)) / distance_miles
    return RouteSummary(
        route_id=route_id,
        distance_miles=distance_miles,
        duration_s=duration_s,
        miles_by_level=tuple(miles_by_level),
        mean_level=mean_level,
    )
