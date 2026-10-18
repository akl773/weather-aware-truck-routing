import pytest

from risk.classification import rain_band, snow_band, wind_band, wind_band_for_load
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


# risk-classification D4: load rules raise the wind band only for loads strictly above the limit.
# fmt: off
LOAD_CASES = [
    # mph,   lb,     level  why
    (55,    0,      N),  # ≥ 55 mph is No Travel for any load
    (45,    30_001, N),  # 45 to 54 mph and > 30,000 lb
    (54.99, 30_001, N),
    (45,    30_000, S),  # exactly 30,000 lb is not "more than"
    (35,    40_001, S),  # 35 to 44 mph and > 40,000 lb
    (44.99, 40_001, S),
    (35,    40_000, H),  # exactly 40,000 lb is not "more than"
    (40,    35_000, H),  # between the two weight limits
    (34.99, 80_000, M),  # below 35 mph no load rule applies
    (20,    80_000, L),
]
# fmt: on


@pytest.mark.parametrize(("mph", "load_lb", "expected"), LOAD_CASES)
def test_load_rules(mph, load_lb, expected):
    assert wind_band_for_load(mph, load_lb) is expected
