"""The spec's risk table and load rules. See docs/decisions/risk-classification.md."""

from bisect import bisect_right
from dataclasses import dataclass

from risk.levels import Level


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
