import pytest

from risk.classification import rain_band, snow_band, wind_band
from risk.levels import Level

L, M, H, S, N = Level.LOW, Level.MODERATE, Level.HIGH, Level.SEVERE, Level.NO_TRAVEL

# risk-classification D1: half-open bands, so each boundary belongs to the higher band.
# Each row holds the two sides of one edge; the formatter would split the pairs apart.
# fmt: off
WIND_CASES = [
    (0, L), (24.99, L),
    (25, M), (34.5, M), (34.99, M),
    (35, H), (44.99, H),
    (45, S), (54.99, S),
    (55, N), (80, N),
]
RAIN_CASES = [
    (0, L), (0.0999, L),
    (0.10, M), (0.2499, M),
    (0.25, H), (0.4999, H),
    (0.50, S), (0.99, S),
    (1.0001, N), (2.5, N),
]
SNOW_CASES = [
    (0, L), (0.4999, L),
    (0.5, M), (0.9999, M),
    (1.0, H), (1.9999, H),
    (2.0, S), (2.9999, S),
    (3.0001, N), (6, N),
]
# fmt: on


@pytest.mark.parametrize(("mph", "expected"), WIND_CASES)
def test_wind_bands(mph, expected):
    assert wind_band(mph) is expected


@pytest.mark.parametrize(("in_hr", "expected"), RAIN_CASES)
def test_rain_bands(in_hr, expected):
    assert rain_band(in_hr) is expected


@pytest.mark.parametrize(("in_hr", "expected"), SNOW_CASES)
def test_snow_bands(in_hr, expected):
    assert snow_band(in_hr) is expected


# risk-classification D2: the No Travel edge keeps each row's own operator.
def test_wind_at_exactly_55_is_no_travel():
    assert wind_band(55) is N


def test_rain_at_exactly_1_00_is_severe():
    assert rain_band(1.00) is S


def test_snow_at_exactly_3_0_is_severe():
    assert snow_band(3.0) is S


@pytest.mark.parametrize("band", [wind_band, rain_band, snow_band])
def test_bands_never_decrease_as_the_value_rises(band):
    values = [step / 100 for step in range(0, 8000)]
    levels = [band(value) for value in values]
    assert levels == sorted(levels)
