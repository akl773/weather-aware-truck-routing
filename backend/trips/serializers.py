"""Plan request and response shapes (plan-api.md). Every number sent is the number shown."""

import math
from datetime import datetime, timedelta
from typing import Any

from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from providers.geo import Point, haversine_mi
from risk.levels import Level
from risk.recommendation import RankingKey, ranking_values
from risk.scoring import display_round
from trips.checkpoints import DEFAULT_INTERVAL_MI, INTERVALS_MI
from trips.corridor import Corridor, Frame
from trips.plan import ROUTE_IDS, Plan, PlannedCheckpoint, PlannedRoute, Readings

MAX_LOAD_LB = 80_000
DEPARTURE_PAST = timedelta(hours=1)
DEPARTURE_AHEAD = timedelta(days=7)
MIN_TRIP_MI = 1.0
MAX_PATHS = 3
MAX_PATH_POINTS = 5_000


class PlaceSerializer(serializers.Serializer):
    label = serializers.CharField(max_length=200)
    lat = serializers.FloatField(min_value=-90, max_value=90)
    lon = serializers.FloatField(min_value=-180, max_value=180)


class AwareDateTimeField(serializers.DateTimeField):
    """An ISO 8601 date-time that must carry its UTC offset (D1)."""

    def to_internal_value(self, value: Any):
        parsed = value if isinstance(value, datetime) else None
        if isinstance(value, str):
            try:
                parsed = parse_datetime(value)
            except ValueError:
                parsed = None  # A well-formed but impossible date; DRF rejects it below.
        if parsed is not None and parsed.tzinfo is None:
            raise serializers.ValidationError(
                "Include the UTC offset, e.g. 2026-10-20T06:00:00-05:00."
            )
        return super().to_internal_value(value)


class TripTimingSerializer(serializers.Serializer):
    """Departure and load, shared by the plan and its corridor (D1, corridor-heatmap D3)."""

    departure = AwareDateTimeField()
    load_lb = serializers.IntegerField(min_value=0, max_value=MAX_LOAD_LB)

    def validate_departure(self, value):
        now = self.context["now"]
        if value < now - DEPARTURE_PAST:
            raise serializers.ValidationError("Departure can be at most one hour ago.")
        if value > now + DEPARTURE_AHEAD:
            raise serializers.ValidationError(
                "Departure can be at most 7 days ahead; the forecast does not reach further."
            )
        return value


class PlanRequestSerializer(TripTimingSerializer):
    origin = PlaceSerializer()
    destination = PlaceSerializer()
    interval_mi = serializers.ChoiceField(choices=INTERVALS_MI, default=DEFAULT_INTERVAL_MI)

    def validate(self, attrs):
        origin = Point(attrs["origin"]["lat"], attrs["origin"]["lon"])
        destination = Point(attrs["destination"]["lat"], attrs["destination"]["lon"])
        if haversine_mi(origin, destination) < MIN_TRIP_MI:
            raise serializers.ValidationError(
                "Origin and destination must be at least a mile apart."
            )
        return attrs


@extend_schema_field(
    {
        "type": "array",
        "minItems": 2,
        "maxItems": MAX_PATH_POINTS,
        "items": {"type": "array", "items": {"type": "number"}, "minItems": 2, "maxItems": 3},
        "description": "[longitude, latitude] or a plan path's [longitude, latitude, mile] points.",
    }
)
class PathField(serializers.Field):
    """A route path as the plan sends it, checked in bulk: a path has thousands of points."""

    def to_internal_value(self, data: Any) -> list[Point]:
        if not isinstance(data, list):
            raise serializers.ValidationError("A path must be a list of points.")
        if not 2 <= len(data) <= MAX_PATH_POINTS:
            raise serializers.ValidationError(
                f"A path needs 2 to {MAX_PATH_POINTS:,} points; this one has {len(data):,}."
            )
        points = []
        for i, item in enumerate(data):
            if (
                not isinstance(item, list)
                or len(item) not in (2, 3)
                or not all(
                    isinstance(v, int | float) and not isinstance(v, bool) and math.isfinite(v)
                    for v in item
                )
                or not (-180 <= item[0] <= 180 and -90 <= item[1] <= 90)
            ):
                raise serializers.ValidationError(
                    f"Point {i} must be [longitude, latitude] with valid coordinates."
                )
            points.append(Point(float(item[1]), float(item[0])))
        return points


class CorridorRequestSerializer(TripTimingSerializer):
    paths = serializers.ListField(child=PathField(), min_length=1, max_length=MAX_PATHS)


# --- Response ------------------------------------------------------------------------------------


class ReadingsSerializer(serializers.Serializer):
    wind_mph = serializers.FloatField(allow_null=True)
    gust_mph = serializers.FloatField(allow_null=True)
    rain_in_hr = serializers.FloatField(allow_null=True)
    snow_in_hr = serializers.FloatField(allow_null=True)


class CheckpointSerializer(serializers.Serializer):
    mile = serializers.FloatField()
    lat = serializers.FloatField()
    lon = serializers.FloatField()
    eta = serializers.DateTimeField()
    owned_from_mi = serializers.FloatField()
    owned_to_mi = serializers.FloatField()
    readings = ReadingsSerializer()
    level = serializers.IntegerField(
        allow_null=True, min_value=0, max_value=4, help_text="0 Low to 4 No Travel; null unknown."
    )
    drivers = serializers.ListField(child=serializers.ChoiceField(choices=["wind", "rain", "snow"]))
    gusty = serializers.BooleanField()


class MilesByLevelSerializer(serializers.Serializer):
    low = serializers.FloatField()
    moderate = serializers.FloatField()
    high = serializers.FloatField()
    severe = serializers.FloatField()
    no_travel = serializers.FloatField()
    unknown = serializers.FloatField()


class SummarySerializer(serializers.Serializer):
    distance_mi = serializers.FloatField()
    duration_min = serializers.IntegerField()
    miles_by_level = MilesByLevelSerializer()
    mean_level = serializers.FloatField(allow_null=True, help_text="0 to 4; null if all unknown.")


class RouteSerializer(serializers.Serializer):
    id = serializers.ChoiceField(choices=ROUTE_IDS)
    fallback = serializers.BooleanField(help_text="Forced through a via point (routing D4).")
    path = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField(), min_length=3, max_length=3),
        help_text="[longitude, latitude, mile] for each point of the simplified route.",
    )
    summary = SummarySerializer()
    checkpoints = CheckpointSerializer(many=True)


class RecommendationSerializer(serializers.Serializer):
    route_id = serializers.ChoiceField(choices=ROUTE_IDS)
    ranking = serializers.ListField(child=serializers.ChoiceField(choices=ROUTE_IDS))
    decided_by = serializers.ChoiceField(
        choices=[key.value for key in RankingKey],
        allow_null=True,
        help_text="The first ranking key separating the top two routes; null if nothing does.",
    )
    reason = serializers.CharField()
    all_routes_cross_no_travel = serializers.BooleanField()


class WeatherWindowSerializer(serializers.Serializer):
    start = serializers.DateTimeField()
    hours = serializers.IntegerField()


class PlanResponseSerializer(serializers.Serializer):
    routes = RouteSerializer(many=True)
    recommendation = RecommendationSerializer()
    weather = WeatherWindowSerializer()


def _checkpoint(c: PlannedCheckpoint) -> dict[str, Any]:
    return {
        "mile": display_round(c.mile, 1),
        "lat": round(c.point.lat, 5),
        "lon": round(c.point.lon, 5),
        "eta": c.eta,
        "owned_from_mi": display_round(c.owned_from_mi, 1),
        "owned_to_mi": display_round(c.owned_to_mi, 1),
        "readings": {
            "wind_mph": c.readings.wind_mph,
            "gust_mph": c.readings.gust_mph,
            "rain_in_hr": c.readings.rain_in_hr,
            "snow_in_hr": c.readings.snow_in_hr,
        },
        "level": None if c.level is None else int(c.level),
        "drivers": [str(d) for d in c.drivers],
        "gusty": c.gusty,
    }


def _route(r: PlannedRoute) -> dict[str, Any]:
    s = r.summary
    ranked = ranking_values(s)
    return {
        "id": r.id,
        "fallback": r.fallback,
        "path": [list(p) for p in r.path],
        "summary": {
            "distance_mi": display_round(s.distance_miles, 1),
            # The same rounding the ranking compares (recommendation D4).
            "duration_min": int(ranked[RankingKey.DURATION]),
            "miles_by_level": {
                "low": display_round(s.miles_at(Level.LOW), 1),
                "moderate": display_round(s.miles_at(Level.MODERATE), 1),
                "high": ranked[RankingKey.HIGH_MILES],
                "severe": ranked[RankingKey.SEVERE_MILES],
                "no_travel": ranked[RankingKey.NO_TRAVEL_MILES],
                "unknown": ranked[RankingKey.UNKNOWN_MILES],
            },
            "mean_level": None if s.mean_level is None else ranked[RankingKey.MEAN_LEVEL],
        },
        "checkpoints": [_checkpoint(c) for c in r.checkpoints],
    }


def plan_response(plan: Plan) -> dict[str, Any]:
    rec = plan.recommendation
    return {
        "routes": [_route(r) for r in plan.routes],
        "recommendation": {
            "route_id": rec.recommended.route_id,
            "ranking": [s.route_id for s in rec.ranked],
            "decided_by": None if rec.decided_by is None else str(rec.decided_by),
            "reason": rec.reason,
            "all_routes_cross_no_travel": rec.all_routes_cross_no_travel,
        },
        "weather": {"start": plan.weather_start, "hours": plan.weather_hours},
    }


class FrameSerializer(serializers.Serializer):
    hour = serializers.IntegerField(help_text="Hours after departure, 0 to 48.")
    level = serializers.ListField(
        child=serializers.IntegerField(allow_null=True, min_value=0, max_value=4),
        help_text="Each cell's level, in cell order; null unknown.",
    )
    wind_mph = serializers.ListField(child=serializers.FloatField(allow_null=True))
    gust_mph = serializers.ListField(child=serializers.FloatField(allow_null=True))
    rain_in_hr = serializers.ListField(child=serializers.FloatField(allow_null=True))
    snow_in_hr = serializers.ListField(child=serializers.FloatField(allow_null=True))


class CorridorResponseSerializer(serializers.Serializer):
    cell_deg = serializers.FloatField(help_text="Cell width and height in degrees.")
    cells = serializers.ListField(
        child=serializers.ListField(child=serializers.FloatField(), min_length=2, max_length=2),
        help_text="[longitude, latitude] of each cell's centre.",
    )
    start = serializers.DateTimeField(help_text="The departure: hour 0.")
    frames = FrameSerializer(many=True)


def _readings_column(readings: tuple[Readings, ...], name: str) -> list[float | None]:
    return [getattr(r, name) for r in readings]


def corridor_response(
    corridor: Corridor, frames: tuple[Frame, ...], departure: datetime
) -> dict[str, Any]:
    return {
        "cell_deg": corridor.cell_deg,
        "cells": [[c.lon, c.lat] for c in corridor.cells],
        "start": departure,
        "frames": [
            {
                "hour": f.hour,
                "level": [None if level is None else int(level) for level in f.levels],
                **{
                    name: _readings_column(f.readings, name)
                    for name in ("wind_mph", "gust_mph", "rain_in_hr", "snow_in_hr")
                },
            }
            for f in frames
        ],
    }
