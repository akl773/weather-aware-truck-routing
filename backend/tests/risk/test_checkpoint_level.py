import math

import pytest

from risk.classification import Condition, Conditions, classify
from risk.levels import Level

CALM = {"wind_mph": 5, "gust_mph": 8, "rain_in_hr": 0, "snow_in_hr": 0}
LIGHT_LOAD = 20_000


def conditions(**overrides) -> Conditions:
    return Conditions(**{**CALM, **overrides})


def test_calm_checkpoint_is_low_with_no_drivers():
    risk = classify(conditions(), LIGHT_LOAD)

    assert risk.level is Level.LOW
    assert risk.drivers == ()


# risk-classification D5: the worst condition sets the level and is named as the driver.
def test_level_is_the_worst_condition():
    risk = classify(conditions(wind_mph=30, gust_mph=33, rain_in_hr=0.3), LIGHT_LOAD)

    assert (risk.wind, risk.rain, risk.snow) == (Level.MODERATE, Level.HIGH, Level.LOW)
    assert risk.level is Level.HIGH
    assert risk.drivers == (Condition.RAIN,)


def test_tied_conditions_are_all_drivers():
    risk = classify(conditions(wind_mph=46, gust_mph=50, snow_in_hr=2.5), LIGHT_LOAD)

    assert risk.level is Level.SEVERE
    assert risk.drivers == (Condition.WIND, Condition.SNOW)


def test_load_rules_apply_to_the_checkpoint_level():
    risk = classify(conditions(wind_mph=46, gust_mph=50), load_lb=35_000)

    assert risk.level is Level.NO_TRAVEL
    assert risk.drivers == (Condition.WIND,)


# risk-classification D3: gusts raise a flag, never the level.
def test_gust_flag_set_when_gusts_reach_a_higher_band():
    risk = classify(conditions(wind_mph=20, gust_mph=30), LIGHT_LOAD)

    assert risk.gusty
    assert risk.level is Level.LOW


def test_gust_flag_not_set_when_gusts_stay_in_the_same_band():
    risk = classify(conditions(wind_mph=30, gust_mph=34), LIGHT_LOAD)

    assert not risk.gusty


def test_gust_flag_counts_load_rules():
    # Sustained 40 mph is High for 35,000 lb; gusts of 46 mph would be No Travel at that load.
    risk = classify(conditions(wind_mph=40, gust_mph=46), load_lb=35_000)

    assert risk.gusty
    assert risk.level is Level.HIGH


# risk-classification D6: impossible readings raise instead of reading as Low.
@pytest.mark.parametrize(
    "overrides",
    [
        {"wind_mph": -1},
        {"gust_mph": -0.1},
        {"gust_mph": math.nan},
        {"rain_in_hr": math.nan},
        {"snow_in_hr": math.inf},
        {"wind_mph": True},
        {"rain_in_hr": None},
        {"snow_in_hr": "0.2"},
        pytest.param({"wind_mph": 10**400}, id="wind-too-large-for-a-float"),
    ],
)
def test_rejects_impossible_readings(overrides):
    with pytest.raises(ValueError, match="must be a finite, non-negative number"):
        conditions(**overrides)


@pytest.mark.parametrize(
    "load_lb",
    [-1, math.nan, math.inf, True, None, pytest.param(10**400, id="too-large-for-a-float")],
)
def test_rejects_impossible_loads(load_lb):
    with pytest.raises(ValueError, match="must be a finite, non-negative number"):
        classify(conditions(), load_lb)
