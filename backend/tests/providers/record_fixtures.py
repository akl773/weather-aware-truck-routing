"""Record the Stadia fixtures from the live API (routing D8).

    cd backend && STADIA_API_KEY=... uv run python -m tests.providers.record_fixtures [prefix ...]

With prefixes, only scenarios whose names start with one of them are recorded, e.g. `openmeteo`.

Each scenario runs through the real adapter, so the recording holds exactly the requests the code
makes, including fallbacks. The key is stripped from every saved request. Re-record after changing
request parameters or fallback offsets.
"""

import json
import os
import sys

import django
import httpx

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_SECRET_KEY", "fixture-recorder")
django.setup()

from providers import open_meteo, stadia  # noqa: E402
from providers.errors import NoRouteError  # noqa: E402
from providers.routing import plan_routes  # noqa: E402
from tests.providers.replay import FIXTURES, request_signature  # noqa: E402
from tests.providers.scenarios import (  # noqa: E402
    DENVER,
    LOAD_LB,
    PLACES_SCENARIOS,
    PLAN_DEPARTURE,
    PLAN_INTERVAL_MI,
    PLAN_NOW,
    PLAN_WEATHER_FIXTURE,
    ROUTE_SCENARIOS,
    SALT_LAKE_CITY,
    WEATHER_HOURS,
    WEATHER_SCENARIOS,
    WEATHER_START,
)
from trips.plan import plan_trip  # noqa: E402


class RecordingTransport(httpx.BaseTransport):
    def __init__(self):
        self.inner = httpx.HTTPTransport()
        self.recorded: list[dict] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        response = self.inner.handle_request(request)
        response.read()
        self.recorded.append(
            {
                "request": request_signature(request),
                "response": {"status": response.status_code, "body": response.json()},
            }
        )
        return response


def record(name: str, run, base_url: str = stadia.BASE_URL) -> None:
    wanted = sys.argv[1:]
    if wanted and not any(name.startswith(prefix) for prefix in wanted):
        return
    transport = RecordingTransport()
    client = httpx.Client(base_url=base_url, timeout=60, transport=transport)
    try:
        run(client)
    except NoRouteError as exc:
        print(f"{name}: NoRouteError({exc})")
    text = json.dumps(transport.recorded, separators=(",", ":"))
    secret = os.environ.get("STADIA_API_KEY")
    if secret and secret in text:
        sys.exit(f"{name}: the API key leaked into the recording; nothing written")
    (FIXTURES / f"{name}.json").write_text(text + "\n")
    print(f"{name}: {len(transport.recorded)} requests, {len(text) // 1024} KB")


def main() -> None:
    from django.test.utils import override_settings

    # Record from the provider, never from a warm cache.
    with override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    ):
        key = os.environ.get("STADIA_API_KEY", "")
        for name, (origin, destination) in ROUTE_SCENARIOS.items():
            record(
                name,
                lambda c, o=origin, d=destination: plan_routes(
                    stadia.StadiaMaps(c, key), o, d, LOAD_LB
                ),
            )
        for name, text in PLACES_SCENARIOS.items():
            record(name, lambda c, t=text: stadia.StadiaMaps(c, key).autocomplete(t))
        for name, (points, batch_size) in WEATHER_SCENARIOS.items():
            original = open_meteo.BATCH_SIZE
            open_meteo.BATCH_SIZE = batch_size or original
            try:
                record(
                    name,
                    lambda c, p=points: open_meteo.OpenMeteo(c).hourly(
                        p, WEATHER_START, WEATHER_HOURS
                    ),
                    base_url=open_meteo.BASE_URL,
                )
            finally:
                open_meteo.BATCH_SIZE = original
        live_maps = stadia.StadiaMaps(httpx.Client(base_url=stadia.BASE_URL, timeout=60), key)
        record(
            PLAN_WEATHER_FIXTURE,
            lambda c: plan_trip(
                origin=DENVER,
                destination=SALT_LAKE_CITY,
                departure=PLAN_DEPARTURE,
                load_lb=LOAD_LB,
                interval_mi=PLAN_INTERVAL_MI,
                router=live_maps,
                weather=open_meteo.OpenMeteo(c),
                now=PLAN_NOW,
            ),
            base_url=open_meteo.BASE_URL,
        )


if __name__ == "__main__":
    main()
