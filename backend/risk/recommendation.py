"""Rank route summaries and explain the pick. See docs/decisions/recommendation.md."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from risk.levels import Level
from risk.scoring import RouteSummary, display_round


class RankingKey(StrEnum):
    NO_TRAVEL_MILES = "no_travel_miles"
    SEVERE_MILES = "severe_miles"
    HIGH_MILES = "high_miles"
    MEAN_LEVEL = "mean_level"
    DURATION = "duration"


def ranking_values(summary: RouteSummary) -> dict[RankingKey, float]:
    """Each ranking key at the precision the route cards show (D4)."""
    return {
        # D3: rounded up, so a sliver of No Travel never ties with a clean route.
        RankingKey.NO_TRAVEL_MILES: display_round(summary.miles_at(Level.NO_TRAVEL), 1, up=True),
        RankingKey.SEVERE_MILES: display_round(summary.miles_at(Level.SEVERE), 1),
        RankingKey.HIGH_MILES: display_round(summary.miles_at(Level.HIGH), 1),
        RankingKey.MEAN_LEVEL: display_round(summary.mean_level, 2),
        RankingKey.DURATION: display_round(summary.duration_s / 60, 0),
    }


def ranking_key(summary: RouteSummary) -> tuple[float, ...]:
    """Lexicographic in RankingKey's declaration order, which is the D3 order."""
    values = ranking_values(summary)
    return tuple(values[key] for key in RankingKey)


@dataclass(frozen=True)
class Recommendation:
    ranked: tuple[RouteSummary, ...]
    decided_by: RankingKey | None  # None with a single route or a tie on every key
    reason: str
    all_routes_cross_no_travel: bool

    @property
    def recommended(self) -> RouteSummary:
        return self.ranked[0]


def recommend(summaries: Sequence[RouteSummary]) -> Recommendation:
    if not summaries:
        raise ValueError("a recommendation needs at least one route")
    # sorted() is stable, so routes tied on every key keep the provider's order (D4).
    ranked = tuple(sorted(summaries, key=ranking_key))
    best = ranking_values(ranked[0])
    decided_by, reason = _explain(best, ranking_values(ranked[1]) if len(ranked) > 1 else None)
    return Recommendation(
        ranked=ranked,
        decided_by=decided_by,
        reason=reason,
        # D5: the top route crosses No Travel only if every route does.
        all_routes_cross_no_travel=best[RankingKey.NO_TRAVEL_MILES] > 0,
    )


_REASONS = {
    RankingKey.NO_TRAVEL_MILES: "Fewest No Travel miles: {best} vs {next}",
    RankingKey.SEVERE_MILES: "Fewest Severe miles: {best} vs {next}",
    RankingKey.HIGH_MILES: "Fewest High miles: {best} vs {next}",
    RankingKey.MEAN_LEVEL: "Lowest average risk: {best} vs {next}",
    RankingKey.DURATION: "Fastest at equal risk: {best} vs {next}",
}


def _explain(
    best: dict[RankingKey, float], runner_up: dict[RankingKey, float] | None
) -> tuple[RankingKey | None, str]:
    """D6: name the first key that separated the top two routes, with both values."""
    if runner_up is None:
        return None, "Only one route was found."
    for key in RankingKey:
        if best[key] != runner_up[key]:
            values = {"best": _format(key, best[key]), "next": _format(key, runner_up[key])}
            return key, _REASONS[key].format(**values) + " on the next best route."
    return None, (
        "Tied with the next best route on every measure; listed first by the routing provider."
    )


def _format(key: RankingKey, value: float) -> str:
    if key is RankingKey.DURATION:
        hours, minutes = divmod(int(value), 60)
        return f"{hours} h {minutes} min" if hours else f"{minutes} min"
    if key is RankingKey.MEAN_LEVEL:
        return f"{value:.2f}"
    return f"{value:.1f}"
