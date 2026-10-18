"""The spec's risk table and load rules. See docs/decisions/risk-classification.md."""

import math
from bisect import bisect_right
from dataclasses import dataclass, fields
from enum import StrEnum

from risk.levels import Level

# D7: conversion and interpolation leave readings like 54.99999999999999 next to an edge.
SNAP_DECIMALS = 6


def snap(value: float) -> float:
    return round(value, SNAP_DECIMALS)


@dataclass(frozen=True)
class BandEdges:
    """One row of the risk table.

    `floors` are the lower edges of Moderate, High and Severe. A value equal to a floor belongs to
    the higher band (D1). No Travel starts above `no_travel_at`, or at it when the spec says ≥ (D2).
    """

    floors: tuple[float, float, float]
    no_travel_at: float
    no_travel_inclusive: bool

    def band(self, value: float) -> Level:
        value = snap(value)
        if value > self.no_travel_at or (self.no_travel_inclusive and value == self.no_travel_at):
            return Level.NO_TRAVEL
        return Level(bisect_right(self.floors, value))


# Floors are (Moderate, High, Severe). No Travel: wind ≥ 55, rain > 1.00, snow > 3.0.
WIND_MPH = BandEdges((25, 35, 45), no_travel_at=55, no_travel_inclusive=True)
RAIN_IN_HR = BandEdges((0.10, 0.25, 0.50), no_travel_at=1.00, no_travel_inclusive=False)
SNOW_IN_HR = BandEdges((0.5, 1.0, 2.0), no_travel_at=3.0, no_travel_inclusive=False)


def wind_band(mph: float) -> Level:
    return WIND_MPH.band(mph)


def rain_band(in_hr: float) -> Level:
    return RAIN_IN_HR.band(in_hr)


def snow_band(in_hr: float) -> Level:
    return SNOW_IN_HR.band(in_hr)


@dataclass(frozen=True)
class LoadRule:
    """Wind in `band` with a load strictly heavier than `over_lb` is raised to `raises_to` (D4)."""

    band: Level
    over_lb: float
    raises_to: Level


LOAD_RULES = (
    LoadRule(band=Level.SEVERE, over_lb=30_000, raises_to=Level.NO_TRAVEL),  # wind in [45, 55)
    LoadRule(band=Level.HIGH, over_lb=40_000, raises_to=Level.SEVERE),  # wind in [35, 45)
)


def wind_band_for_load(mph: float, load_lb: float) -> Level:
    band = wind_band(mph)
    for rule in LOAD_RULES:
        if band is rule.band and snap(load_lb) > rule.over_lb:
            return rule.raises_to
    return band


class Condition(StrEnum):
    WIND = "wind"
    RAIN = "rain"
    SNOW = "snow"


def _require_reading(name: str, value: object) -> None:
    # D6: corrupt data must fail loudly; read as zero it would look like a calm, Low checkpoint.
    # bool is an int subclass, so True would otherwise pass as 1.
    valid = isinstance(value, int | float) and not isinstance(value, bool)
    if valid:
        try:
            valid = math.isfinite(value) and value >= 0
        except OverflowError:  # an int too large for a float
            valid = False
    if not valid:
        raise ValueError(f"{name} must be a finite, non-negative number, got {value!r}")


@dataclass(frozen=True)
class Conditions:
    """Weather at one checkpoint at the truck's ETA."""

    wind_mph: float
    gust_mph: float
    rain_in_hr: float
    snow_in_hr: float

    def __post_init__(self) -> None:
        for field in fields(self):
            _require_reading(field.name, getattr(self, field.name))


@dataclass(frozen=True)
class CheckpointRisk:
    wind: Level  # after load rules
    rain: Level
    snow: Level
    level: Level
    drivers: tuple[Condition, ...]
    gusty: bool


def classify(conditions: Conditions, load_lb: float) -> CheckpointRisk:
    _require_reading("load_lb", load_lb)
    bands = {
        Condition.WIND: wind_band_for_load(conditions.wind_mph, load_lb),
        Condition.RAIN: rain_band(conditions.rain_in_hr),
        Condition.SNOW: snow_band(conditions.snow_in_hr),
    }
    # D5: the worst condition sets the level; every condition at that level is a driver.
    level = max(bands.values())
    drivers = tuple(c for c, band in bands.items() if band is level) if level > Level.LOW else ()
    return CheckpointRisk(
        wind=bands[Condition.WIND],
        rain=bands[Condition.RAIN],
        snow=bands[Condition.SNOW],
        level=level,
        drivers=drivers,
        # D3: gusts flag a checkpoint but never change its level.
        gusty=wind_band_for_load(conditions.gust_mph, load_lb) > bands[Condition.WIND],
    )
