import pytest

from risk.levels import Level
from risk.recommendation import RankingKey, recommend
from risk.scoring import RouteSummary, display_round


def route(
    route_id: str,
    *,
    no_travel: float = 0,
    severe: float = 0,
    high: float = 0,
    mean_level: float = 0.5,
    minutes: float = 300,
    distance: float = 300,
) -> RouteSummary:
    low = distance - no_travel - severe - high
    return RouteSummary(
        route_id=route_id,
        distance_miles=distance,
        duration_s=minutes * 60,
        miles_by_level=(low, 0.0, high, severe, no_travel),
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
        (route("w", severe=3), route("l", severe=9, high=0), RankingKey.SEVERE_MILES),
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


def test_levels_line_up_with_the_summary_tuple():
    summary = route("a", no_travel=1, severe=2, high=3)

    assert (summary.miles_at(Level.NO_TRAVEL), summary.miles_at(Level.SEVERE)) == (1, 2)
    assert summary.miles_at(Level.HIGH) == 3
