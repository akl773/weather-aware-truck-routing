"""Open-Meteo adapter: hourly wind, gusts, rain and snow in mph and inches (weather D1 to D6).

Open-Meteo's variable names and hour conventions stop here. Callers get `Series` per lattice point.
"""

import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from providers.cache import fetch_many_cached, request_key
from providers.errors import ProviderError
from providers.geo import Point

BASE_URL = "https://api.open-meteo.com"
TIMEOUT_S = 30.0
TTL_S = 3600
LATTICE_DEG = 0.05
BATCH_SIZE = 100
HOURLY = ("wind_speed_10m", "wind_gusts_10m", "rain", "showers", "snowfall")
# The plan and the 48 h heatmap share one window (D5): the hour before departure plus 49 more.
MIN_WINDOW_H = 50
# Open-Meteo accepts end hours up to the end of today + 15 days (UTC).
RANGE_DAYS = 15


@dataclass(frozen=True)
class Series:
    """Hourly conditions at one lattice point. Values are `None` where the provider has none.

    `times` are when instant values (wind) are valid. `period_times` are when hourly totals and
    maxima (gusts, rain, snow) are valid: the middle of the hour they cover (D3).
    """

    times: tuple[float, ...]
    wind_mph: tuple[float | None, ...]
    gust_mph: tuple[float | None, ...]
    rain_in_hr: tuple[float | None, ...]
    snow_in_hr: tuple[float | None, ...]

    @property
    def period_times(self) -> tuple[float, ...]:
        return tuple(t - 1800 for t in self.times)


def snap(point: Point) -> Point:
    """The lattice point a location reads its weather from (D4)."""

    def to_lattice(value: float) -> float:
        return round(round(value / LATTICE_DEG) * LATTICE_DEG, 4)

    return Point(to_lattice(point.lat), to_lattice(point.lon))


def fetch_window(
    departure: datetime, needed_until: datetime, now: datetime
) -> tuple[datetime, int]:
    """Start hour and length of the window to fetch for a trip (D5).

    Starts on the hour before departure, spans at least 50 hours rounded up to whole days, and is
    clamped to the provider's range.
    """
    hour = departure.astimezone(UTC).replace(minute=0, second=0, microsecond=0)
    start = hour - timedelta(hours=1)
    needed_h = max(MIN_WINDOW_H, math.ceil((needed_until - start).total_seconds() / 3600) + 1)
    hours = 24 * math.ceil(needed_h / 24)
    range_end = now.astimezone(UTC).replace(hour=23, minute=0, second=0, microsecond=0)
    range_end += timedelta(days=RANGE_DAYS)
    hours = min(hours, int((range_end - start).total_seconds() // 3600) + 1)
    if hours <= 0:
        raise ProviderError("The departure is beyond the weather forecast range.")
    return start, hours


def _reading(value: Any) -> float | None:
    """A provider value as a reading, or `None`. Never 0 for a gap, because 0 reads as calm."""
    if value is None:
        return None
    number = float(value)
    return number if math.isfinite(number) else None


def _readings(values: Sequence[Any]) -> tuple[float | None, ...]:
    return tuple(map(_reading, values))


def _sum(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else a + b


def parse_location(data: dict[str, Any]) -> Series:
    hourly = data["hourly"]
    if any(len(hourly[name]) != len(hourly["time"]) for name in HOURLY):
        raise ValueError("hourly arrays differ in length")
    return Series(
        times=tuple(float(t) for t in hourly["time"]),
        wind_mph=_readings(hourly["wind_speed_10m"]),
        gust_mph=_readings(hourly["wind_gusts_10m"]),
        rain_in_hr=tuple(
            map(_sum, _readings(hourly["rain"]), _readings(hourly["showers"]), strict=True)
        ),
        snow_in_hr=_readings(hourly["snowfall"]),
    )


class OpenMeteo:
    def __init__(self, client: httpx.Client):
        self.client = client

    def hourly(self, points: Iterable[Point], start: datetime, hours: int) -> dict[Point, Series]:
        """Series for each distinct lattice point the `points` snap to, keyed by lattice point."""
        start_text = start.astimezone(UTC).strftime("%Y-%m-%dT%H:%M")
        lattice = sorted({snap(p) for p in points})
        keys = {
            request_key("openmeteo:hourly:v1", [p.lat, p.lon, start_text, hours]): p
            for p in lattice
        }
        return fetch_many_cached(keys, TTL_S, lambda missing: self._fetch(missing, start, hours))

    def _fetch(self, points: Sequence[Point], start: datetime, hours: int) -> dict[Point, Series]:
        end = start + timedelta(hours=hours - 1)
        result: dict[Point, Series] = {}
        for i in range(0, len(points), BATCH_SIZE):
            batch = points[i : i + BATCH_SIZE]
            data = self._request(batch, start, end)
            locations = data if isinstance(data, list) else [data]
            if len(locations) != len(batch):
                raise ProviderError("The weather provider returned the wrong number of locations.")
            try:
                result.update(zip(batch, map(parse_location, locations), strict=True))
            except (KeyError, TypeError, ValueError) as exc:
                raise ProviderError("The weather provider returned an unreadable answer.") from exc
        return result

    def _request(self, batch: Sequence[Point], start: datetime, end: datetime) -> Any:
        form = {
            "latitude": ",".join(f"{p.lat:g}" for p in batch),
            "longitude": ",".join(f"{p.lon:g}" for p in batch),
            "hourly": ",".join(HOURLY),
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timeformat": "unixtime",
            "timezone": "GMT",
            "start_hour": start.strftime("%Y-%m-%dT%H:%M"),
            "end_hour": end.strftime("%Y-%m-%dT%H:%M"),
        }
        try:
            response = self.client.post("/v1/forecast", data=form)
        except httpx.HTTPError as exc:
            raise ProviderError("The weather provider could not be reached.") from exc
        if response.status_code == 429:
            raise ProviderError(
                "The weather provider is rate limiting requests. Try again shortly."
            )
        if not response.is_success:
            raise ProviderError("The weather provider failed to answer.")
        try:
            return response.json()
        except ValueError as exc:
            raise ProviderError("The weather provider returned an unreadable answer.") from exc


def default() -> OpenMeteo:
    """The app's client. Tests replace this function to replay recorded responses."""
    return OpenMeteo(httpx.Client(base_url=BASE_URL, timeout=TIMEOUT_S))
