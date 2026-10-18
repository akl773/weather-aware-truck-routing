"""Compose routes, checkpoints, weather and the risk engine into a trip plan (plan-api.md)."""

from dataclasses import dataclass
from datetime import datetime, timedelta

from providers.geo import Point, simplify
from providers.open_meteo import OpenMeteo, Series, fetch_window
from providers.routing import Route, Router, plan_routes
from risk.classification import Condition, Conditions, classify
from risk.levels import Level
from risk.recommendation import Recommendation, recommend
from risk.scoring import (
    CheckpointLevel,
    RouteSummary,
    display_round,
    owned_stretches,
    summarize_route,
)
from trips.checkpoints import place_checkpoints, value_at

ROUTE_IDS = ("A", "B", "C")
PATH_TOLERANCE_DEG = 0.0005
# The heatmap covers 48 hours from departure; the plan's weather window must too (weather D5).
HEATMAP_HOURS = 48


@dataclass(frozen=True)
class Readings:
    """Conditions at a checkpoint's ETA, rounded as shown (D2). `None` is unknown."""

    wind_mph: float | None
    gust_mph: float | None
    rain_in_hr: float | None
    snow_in_hr: float | None


@dataclass(frozen=True)
class PlannedCheckpoint:
    mile: float
    point: Point
    eta: datetime
    owned_from_mi: float
    owned_to_mi: float
    readings: Readings
    level: Level | None
    drivers: tuple[Condition, ...]
    gusty: bool


@dataclass(frozen=True)
class PlannedRoute:
    id: str
    fallback: bool
    path: tuple[tuple[float, float, float], ...]  # (longitude, latitude, mile)
    checkpoints: tuple[PlannedCheckpoint, ...]
    summary: RouteSummary


@dataclass(frozen=True)
class Plan:
    routes: tuple[PlannedRoute, ...]
    recommendation: Recommendation
    weather_start: datetime
    weather_hours: int


def _shown(value: float | None, places: int) -> float | None:
    return None if value is None else display_round(value, places)


def readings_at(series: Series, eta: datetime) -> Readings:
    """Conditions at `eta`, interpolated (checkpoints-and-eta D4) and rounded as shown (D2)."""
    t = eta.timestamp()
    return Readings(
        wind_mph=_shown(value_at(series.times, series.wind_mph, t), 1),
        gust_mph=_shown(value_at(series.period_times, series.gust_mph, t), 1),
        rain_in_hr=_shown(value_at(series.period_times, series.rain_in_hr, t), 2),
        snow_in_hr=_shown(value_at(series.period_times, series.snow_in_hr, t), 2),
    )


def classify_checkpoint(
    readings: Readings, load_lb: float
) -> tuple[Level | None, tuple[Condition, ...], bool]:
    """Level, driver conditions and gust flag (D3).

    Without a full forecast the level is unknown, unless a known reading is already No Travel: the
    level is the worst condition (risk-classification D5), so nothing missing could change it.
    """
    wind, rain, snow = readings.wind_mph, readings.rain_in_hr, readings.snow_in_hr
    complete = wind is not None and rain is not None and snow is not None
    # A missing gust only clears the flag: gusts never set the level (risk-classification D3).
    gust = wind if readings.gust_mph is None or wind is None else readings.gust_mph
    # Missing readings stand in as calm only to ask whether the known ones reach No Travel; that
    # answer is used, and any other one is discarded.
    risk = classify(
        Conditions(*(0.0 if v is None else v for v in (wind, gust, rain, snow))), load_lb
    )
    if complete or risk.level is Level.NO_TRAVEL:
        return risk.level, risk.drivers, risk.gusty
    return None, (), False


def _path(route: Route) -> tuple[tuple[float, float, float], ...]:
    """Simplified geometry with the mile of every kept point (D4)."""
    return tuple(
        (
            round(route.points[i].lon, 5),
            round(route.points[i].lat, 5),
            display_round(route.cum_mi[i], 2),
        )
        for i in simplify(route.points, PATH_TOLERANCE_DEG)
    )


def plan_trip(
    *,
    origin: Point,
    destination: Point,
    departure: datetime,
    load_lb: float,
    interval_mi: int,
    router: Router,
    weather: OpenMeteo,
    now: datetime,
) -> Plan:
    routes = plan_routes(router, origin, destination, load_lb)
    placed = [place_checkpoints(route, interval_mi, departure) for route in routes]

    last_eta = max(checkpoints[-1].eta for checkpoints in placed)
    needed_until = max(last_eta, departure + timedelta(hours=HEATMAP_HOURS))
    start, hours = fetch_window(departure, needed_until, now)
    series = weather.hourly(
        (checkpoint.point for checkpoints in placed for checkpoint in checkpoints), start, hours
    )

    planned: list[PlannedRoute] = []
    for route_id, route, checkpoints in zip(ROUTE_IDS, routes, placed, strict=False):
        bounds = owned_stretches([c.mile for c in checkpoints], route.distance_mi)
        rows = []
        for checkpoint, (owned_from, owned_to) in zip(checkpoints, bounds, strict=True):
            readings = readings_at(series[checkpoint.point], checkpoint.eta)
            level, drivers, gusty = classify_checkpoint(readings, load_lb)
            rows.append(
                PlannedCheckpoint(
                    mile=checkpoint.mile,
                    point=checkpoint.point,
                    eta=checkpoint.eta,
                    owned_from_mi=owned_from,
                    owned_to_mi=owned_to,
                    readings=readings,
                    level=level,
                    drivers=drivers,
                    gusty=gusty,
                )
            )
        summary = summarize_route(
            route_id,
            route.distance_mi,
            route.duration_s,
            [CheckpointLevel(row.mile, row.level) for row in rows],
        )
        planned.append(
            PlannedRoute(
                id=route_id,
                fallback=route.via is not None,
                path=_path(route),
                checkpoints=tuple(rows),
                summary=summary,
            )
        )
    return Plan(
        routes=tuple(planned),
        recommendation=recommend([route.summary for route in planned]),
        weather_start=start,
        weather_hours=hours,
    )
