"""Stadia Maps adapter: Valhalla truck routing and place autocomplete (routing D1, D2, D6).

Valhalla's field names, units and error codes stop here. Callers get `Route` and `Place`.
"""

import functools
import itertools
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx
from django.conf import settings

from providers.cache import fetch_cached, request_key
from providers.errors import NoRouteError, ProviderError
from providers.geo import Point, decode_polyline, haversine_mi
from providers.routing import Route

log = logging.getLogger(__name__)

BASE_URL = "https://api.stadiamaps.com"
TIMEOUT_S = 20.0
ROUTE_TTL_S = 6 * 3600
PLACES_TTL_S = 7 * 86400
PLACES_COUNTRIES = "US,CA,MX"
PLACES_LIMIT = 6

# A typical empty tractor with a 53 ft van trailer (routing D2).
TRACTOR_TRAILER_LB = 35_000
KG_PER_LB = 0.45359237

# Valhalla error codes that mean "no route exists", as opposed to a failed request.
NO_ROUTE_ERRORS = {
    170: "These places are not connected by road.",
    171: "No road found near one of the places.",
    442: "No truck route found between these places.",
    154: "This trip is longer than the routing provider allows.",
}


def gross_weight_tonnes(load_lb: float) -> float:
    """Whole-vehicle weight in metric tons, as Valhalla's truck `weight` expects (routing D2)."""
    return round((TRACTOR_TRAILER_LB + load_lb) * KG_PER_LB / 1000, 2)


@dataclass(frozen=True)
class Place:
    label: str
    point: Point


def parse_trip(trip: dict[str, Any]) -> Route:
    """Join a Valhalla trip's legs into one `Route` with cumulative miles and seconds (D3).

    Each maneuver's length and time are spread over its shape points in proportion to their
    great-circle length, so the last point carries exactly the provider's totals.
    """
    points: list[Point] = []
    cum_mi: list[float] = []
    cum_s: list[float] = []
    for leg in trip["legs"]:
        shape = decode_polyline(leg["shape"])
        offset = len(points)
        if points:
            offset -= 1  # A leg starts where the previous one ended; keep that point once.
            shape = shape[1:]
        else:
            cum_mi.append(0.0)
            cum_s.append(0.0)
        points.extend(shape)
        for maneuver in leg["maneuvers"]:
            start = offset + maneuver["begin_shape_index"]
            end = offset + maneuver["end_shape_index"]
            if end <= start:
                continue  # The arrival maneuver has no extent.
            seg = [haversine_mi(a, b) for a, b in itertools.pairwise(points[start : end + 1])]
            total = sum(seg)
            base_mi, base_s = cum_mi[-1], cum_s[-1]
            run = 0.0
            for i, length in enumerate(seg, start=1):
                run += length
                share = run / total if total > 0 else i / len(seg)
                cum_mi.append(base_mi + maneuver["length"] * share)
                cum_s.append(base_s + maneuver["time"] * share)
    if len(cum_mi) != len(points):
        raise ProviderError("Routing provider returned maneuvers that do not cover the shape.")
    return Route(tuple(points), tuple(cum_mi), tuple(cum_s))


class StadiaMaps:
    def __init__(self, client: httpx.Client, api_key: str):
        self.client = client
        self.api_key = api_key

    def routes(self, stops: Sequence[Point], load_lb: float, alternates: int) -> list[Route]:
        locations = [
            # Intermediate stops are pass-through: no stop, no U-turn (routing D4).
            {"lat": p.lat, "lon": p.lon, "type": "break" if i in (0, len(stops) - 1) else "through"}
            for i, p in enumerate(stops)
        ]
        body: dict[str, Any] = {
            "locations": locations,
            "costing": "truck",
            "costing_options": {"truck": {"weight": gross_weight_tonnes(load_lb)}},
            "units": "miles",
            "directions_type": "maneuvers",
        }
        if alternates:
            body["alternates"] = alternates
        data = fetch_cached(
            request_key("stadia:route:v1", body),
            ROUTE_TTL_S,
            lambda: self._request("POST", "/route/v1", json=body),
        )
        trips = [data["trip"], *(alt["trip"] for alt in data.get("alternates", []))]
        return [parse_trip(trip) for trip in trips]

    def autocomplete(self, text: str) -> list[Place]:
        params = {"text": text, "boundary.country": PLACES_COUNTRIES, "size": PLACES_LIMIT}
        data = fetch_cached(
            request_key("stadia:autocomplete:v1", params),
            PLACES_TTL_S,
            lambda: self._request("GET", "/geocoding/v1/autocomplete", params=params),
        )
        return [
            Place(
                label=feature["properties"]["label"],
                point=Point(
                    feature["geometry"]["coordinates"][1], feature["geometry"]["coordinates"][0]
                ),
            )
            for feature in data["features"]
        ]

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        params = {**kwargs.pop("params", {}), "api_key": self.api_key}
        try:
            response = self.client.request(method, path, params=params, **kwargs)
        except httpx.HTTPError as exc:
            raise ProviderError("The routing provider could not be reached.") from exc
        if response.is_success:
            return response.json()
        error_code = _error_code(response)
        if error_code in NO_ROUTE_ERRORS:
            raise NoRouteError(NO_ROUTE_ERRORS[error_code])
        log.warning(
            "Stadia %s %s returned %s: %s", method, path, response.status_code, response.text[:300]
        )
        if response.status_code == 429:
            raise ProviderError(
                "The routing provider is rate limiting requests. Try again shortly."
            )
        raise ProviderError("The routing provider failed to answer.")


def _error_code(response: httpx.Response) -> int | None:
    try:
        return response.json().get("error_code")
    except ValueError:
        return None


@functools.cache
def default() -> StadiaMaps:
    """The app's shared client. Tests replace this function to replay recorded responses."""
    if not settings.STADIA_API_KEY:
        raise ProviderError("Routing is not configured: STADIA_API_KEY is missing.")
    return StadiaMaps(httpx.Client(base_url=BASE_URL, timeout=TIMEOUT_S), settings.STADIA_API_KEY)
