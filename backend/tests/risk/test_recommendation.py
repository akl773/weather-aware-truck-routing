import pytest

from risk.recommendation import RankingKey, recommend
from risk.scoring import RouteSummary, display_round


def route(
    route_id: str,
    *,
    no_travel: float = 0,
    severe: float = 0,
    high: float = 0,
    unknown: float = 0,
    mean_level: float | None = 0.5,
    minutes: float = 300,
    distance: float = 300,
) -> RouteSummary:
    low = distance - no_travel - severe - high - unknown
    return RouteSummary(
        route_id=route_id,
        distance_miles=distance,
        duration_s=minutes * 60,
        miles_by_level=(low, 0.0, high, severe, no_travel),
        unknown_miles=unknown,
        mean_level=mean_level,
    )


def ranked_ids(*routes: RouteSummary) -> list[str]:
    return [summary.route_id for summary in recommend(routes).ranked]


# recommendation D3: (No Travel, Severe, High, mean level, duration), in that order.
def test_rank_puts_no_travel_before_everything_else():
    blocked = route("blocked", no_travel=5, minutes=200)
    stormy = route("stormy", severe=120, high=80, mean_level=2.4, minutes=400)

    result = recommend([blocked, stormy])

    assert result.recommended.route_id == "stormy"
    assert result.decided_by is RankingKey.NO_TRAVEL_MILES


@pytest.mark.parametrize(
    ("winner", "loser", "deciding_key"),
    [
        (route("w", severe=3), route("l", severe=9), RankingKey.SEVERE_MILES),
        (route("w", high=10), route("l", high=40), RankingKey.HIGH_MILES),
        (route("w", mean_level=0.4), route("l", mean_level=0.9), RankingKey.MEAN_LEVEL),
        (route("w", minutes=290), route("l", minutes=330), RankingKey.DURATION),
    ],
)
def test_rank_falls_through_to_the_first_key_that_differs(winner, loser, deciding_key):
    result = recommend([loser, winner])

    assert result.recommended.route_id == "w"
    assert result.decided_by is deciding_key


def test_rank_severe_miles_outweigh_a_much_faster_route():
    assert ranked_ids(route("fast", severe=1, minutes=200), route("slow", minutes=500)) == [
        "slow",
        "fast",
    ]


# recommendation D4: keys compare at the precision the cards show.
def test_display_round_rounds_halves_up():
    assert display_round(12.25, 1) == 12.3
    assert display_round(0.125, 2) == 0.13
    assert display_round(12.24, 1) == 12.2
    # 2.675 is stored as 2.67499999...; rounding the decimal value keeps the half visible.
    assert display_round(2.675, 2) == 2.68


def test_display_tie_keeps_provider_order_even_when_raw_values_differ():
    # Both show 3.2 Severe miles; the provider's first route is slightly worse underneath.
    provider_first = route("provider-first", severe=3.24)
    provider_second = route("provider-second", severe=3.21)

    result = recommend([provider_first, provider_second])

    assert [summary.route_id for summary in result.ranked] == ["provider-first", "provider-second"]
    assert result.decided_by is None


def test_differences_below_display_precision_tie():
    # 3.21 and 3.24 Severe miles both show as 3.2, so High miles decide.
    a = route("a", severe=3.24, high=10)
    b = route("b", severe=3.21, high=20)

    result = recommend([b, a])

    assert result.recommended.route_id == "a"
    assert result.decided_by is RankingKey.HIGH_MILES


def test_full_tie_keeps_the_provider_order():
    first, second = route("first"), route("second")

    result = recommend([first, second])

    assert ranked_ids(first, second) == ["first", "second"]
    assert result.decided_by is None


# recommendation D5: every route crosses No Travel → still recommend, and flag it.
def test_all_routes_crossing_no_travel_still_recommends_the_least_bad():
    result = recommend([route("a", no_travel=30), route("b", no_travel=4)])

    assert result.recommended.route_id == "b"
    assert result.all_routes_cross_no_travel


def test_flag_is_off_when_any_route_avoids_no_travel():
    result = recommend([route("a", no_travel=30), route("b")])

    assert not result.all_routes_cross_no_travel


# recommendation D6: the reason names the deciding key and both values.
def test_reason_names_the_deciding_key_and_both_values():
    result = recommend([route("a", severe=18.46), route("b", severe=3.2)])

    assert result.reason == "Fewest Severe miles: 3.2 vs 18.5 on the next best route."


def test_reason_formats_duration_in_hours_and_minutes():
    result = recommend([route("a", minutes=340), route("b", minutes=310)])

    assert result.reason == (
        "Fastest at equal risk: 5 h 10 min vs 5 h 40 min on the next best route."
    )


def test_reason_drops_a_zero_minute_part():
    result = recommend([route("a", minutes=120), route("b", minutes=45)])

    assert result.reason == "Fastest at equal risk: 45 min vs 2 h on the next best route."


def test_reason_for_a_single_route():
    result = recommend([route("only")])

    assert result.decided_by is None
    assert result.reason == "Only one route was found."


def test_reason_for_a_full_tie():
    assert recommend([route("a"), route("b")]).reason == (
        "Tied with the next best route on every measure; listed first by the routing provider."
    )


def test_recommend_needs_at_least_one_route():
    with pytest.raises(ValueError, match="at least one route"):
        recommend([])


def test_reason_drops_the_hours_for_trips_under_an_hour():
    result = recommend([route("a", minutes=50), route("b", minutes=45)])

    assert result.reason == "Fastest at equal risk: 45 min vs 50 min on the next best route."


# recommendation D3: No Travel rounds up, so a sliver of it never ties with a clean route.
def test_any_no_travel_mileage_loses_to_a_clean_route():
    sliver = route("sliver", no_travel=0.04)
    clean = route("clean", severe=50)

    result = recommend([sliver, clean])

    assert result.recommended.route_id == "clean"
    assert result.decided_by is RankingKey.NO_TRAVEL_MILES
    assert result.reason == "Fewest No Travel miles: 0.0 vs 0.1 on the next best route."


def test_a_sliver_of_no_travel_on_every_route_sets_the_flag():
    assert recommend(
        [route("a", no_travel=0.04), route("b", no_travel=0.02)]
    ).all_routes_cross_no_travel


# recommendation D7: unknown miles rank right after No Travel miles.
def test_unknown_miles_rank_after_no_travel_and_before_severe():
    unknown = route("unknown", unknown=10)
    severe = route("severe", severe=200)
    no_travel = route("no_travel", no_travel=1)
    assert ranked_ids(no_travel, unknown, severe) == ["severe", "unknown", "no_travel"]


def test_a_sliver_of_unknown_miles_counts():
    result = recommend([route("gap", unknown=0.01), route("known", high=40)])
    assert result.recommended.route_id == "known"
    assert result.decided_by is RankingKey.UNKNOWN_MILES
    assert result.reason == ("Fewest miles without a forecast: 0.0 vs 0.1 on the next best route.")


def test_a_route_with_no_known_mile_ranks_last_on_mean_level():
    # Equal unknown miles, so the mean decides: no known mile counts as all No Travel (4.0).
    blind = route("blind", unknown=100, mean_level=None, distance=100)
    known = route("known", unknown=100, mean_level=0.0, distance=150)
    assert ranked_ids(blind, known) == ["known", "blind"]
    assert recommend([blind, known]).decided_by is RankingKey.MEAN_LEVEL
