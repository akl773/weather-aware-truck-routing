"""Open-Meteo adapter: hourly wind, gusts, rain and snow in mph and inches (weather D1 to D6).

Open-Meteo's variable names, hour conventions and lattice stop here. Callers get a `Series` for each
point they ask about.
"""

import functools
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

    @functools.cached_property
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
    # The last hourly total is valid 30 minutes before the last hour (D3), so it needs half an
    # hour of slack to cover `needed_until`.
    needed_h = (needed_until - start).total_seconds() / 3600
    hours = 24 * math.ceil(max(MIN_WINDOW_H, math.ceil(needed_h + 0.5) + 1) / 24)
    range_end = now.astimezone(UTC).replace(hour=23, minute=0, second=0, microsecond=0)
    range_end += timedelta(days=RANGE_DAYS)
    hours = min(hours, int((range_end - start).total_seconds() // 3600) + 1)
    if hours <= 0:
        # Callers validate the departure before asking, so this is a programming error.
        raise ValueError("The departure is beyond the weather forecast range.")
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
        """The series for each point, read from the lattice point it snaps to (D4)."""
        start = start.astimezone(UTC)
        points = list(points)
        start_text = start.strftime("%Y-%m-%dT%H:%M")
        keys = {
            request_key("openmeteo:hourly:v1", [p.lat, p.lon, start_text, hours]): p
            for p in sorted({snap(p) for p in points})
        }
        answers = fetch_many_cached(
            keys, TTL_S, lambda batch: self._fetch(batch, start, hours), BATCH_SIZE
        )
        try:
            by_lattice = {p: parse_location(answer) for p, answer in answers.items()}
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("The weather provider returned an unreadable answer.") from exc
        return {p: by_lattice[snap(p)] for p in points}

    def _fetch(self, batch: Sequence[Point], start: datetime, hours: int) -> dict[Point, Any]:
        """One request for a batch of lattice points: the raw answer for each (D6)."""
        data = self._request(batch, start, start + timedelta(hours=hours - 1))
        locations = data if isinstance(data, list) else [data]
        if len(locations) != len(batch):
            raise ProviderError("The weather provider returned the wrong number of locations.")
        return dict(zip(batch, locations, strict=True))

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


@functools.cache
def default() -> OpenMeteo:
    """The app's shared client. Tests replace this function to replay recorded responses."""
    return OpenMeteo(httpx.Client(base_url=BASE_URL, timeout=TIMEOUT_S))
