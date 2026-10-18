"""Owned miles and route summaries. See docs/decisions/recommendation.md."""

import math
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal
from itertools import pairwise

from risk.levels import Level


def display_round(value: float, places: int, *, up: bool = False) -> float:
    """Round half up on the decimal value, the one rounding the ranking and the API share (D4).

    `round()` rounds 12.25 to 12.2 and JavaScript's `toFixed` gives 12.3; this gives 12.3, and the
    UI prints the result as is. `up=True` rounds any remainder up instead (No Travel miles, D3).
    """
    if not math.isfinite(value):
        raise ValueError(f"only finite values can be displayed, got {value!r}")
    mode = ROUND_CEILING if up else ROUND_HALF_UP
    return float(Decimal(repr(value)).quantize(Decimal(1).scaleb(-places), mode))


@dataclass(frozen=True)
class CheckpointLevel:
    mile: float  # distance from the origin along the route
    level: Level | None  # None when the weather at the ETA is unknown (D7)


def owned_stretches(
    checkpoint_miles: Sequence[float], route_miles: float
) -> list[tuple[float, float]]:
    """Where each checkpoint's stretch of road starts and ends (D1).

    Boundaries sit halfway between neighbouring checkpoints; the first stretch starts at the origin
    and the last ends at the destination, so the stretches tile the route.
    """
    if not checkpoint_miles:
        raise ValueError("a route needs at least one checkpoint")
    if not all(math.isfinite(mile) for mile in [*checkpoint_miles, route_miles]):
        raise ValueError("checkpoint miles and route length must be finite")
    if route_miles <= 0:
        raise ValueError("route length must be positive")
    # D1: a duplicate would own zero miles and its level would vanish from the summary.
    if any(later <= earlier for earlier, later in pairwise(checkpoint_miles)):
        raise ValueError("checkpoint miles must be strictly increasing along the route")
    if checkpoint_miles[0] < 0 or checkpoint_miles[-1] > route_miles:
        raise ValueError("checkpoints must lie within the route")

    midpoints = [(a + b) / 2 for a, b in pairwise(checkpoint_miles)]
    return list(pairwise([0.0, *midpoints, route_miles]))


def owned_miles(checkpoint_miles: Sequence[float], route_miles: float) -> list[float]:
    """Miles of road each checkpoint speaks for (D1); they always sum to `route_miles`."""
    return [end - start for start, end in owned_stretches(checkpoint_miles, route_miles)]


@dataclass(frozen=True)
class RouteSummary:
    route_id: str
    distance_miles: float
    duration_s: float
    miles_by_level: tuple[float, ...]  # indexed by Level
    unknown_miles: float  # owned by checkpoints whose weather is unknown (D7)
    # 0 (all Low) to 4 (all No Travel), weighted by owned miles over the known miles only (D2, D7);
    # None when no mile of the route has a known level.
    mean_level: float | None

    def miles_at(self, level: Level) -> float:
        return self.miles_by_level[level]


def summarize_route(
    route_id: str,
    distance_miles: float,
    duration_s: float,
    checkpoints: Sequence[CheckpointLevel],
) -> RouteSummary:
    if not math.isfinite(duration_s) or duration_s < 0:
        raise ValueError(f"duration must be finite and non-negative, got {duration_s!r}")
    owned = owned_miles([checkpoint.mile for checkpoint in checkpoints], distance_miles)
    miles_by_level = [0.0] * len(Level)
    unknown_miles = 0.0
    for checkpoint, miles in zip(checkpoints, owned, strict=True):
        if checkpoint.level is None:
            unknown_miles += miles
        else:
            miles_by_level[checkpoint.level] += miles
    # D2: weighted by owned miles, so the sampling interval does not change the mean.
    # D7: over known miles only, so unknown road is neither calm nor dangerous here.
    known_miles = sum(miles_by_level)
    mean_level = (
        sum(level * miles for level, miles in enumerate(miles_by_level)) / known_miles
        if known_miles > 0
        else None
    )
    return RouteSummary(
        route_id=route_id,
        distance_miles=distance_miles,
        duration_s=duration_s,
        miles_by_level=tuple(miles_by_level),
        unknown_miles=unknown_miles,
        mean_level=mean_level,
    )
