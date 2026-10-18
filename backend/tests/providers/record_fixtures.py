"""Record the Stadia fixtures from the live API (routing D8).

    cd backend && STADIA_API_KEY=... uv run python -m tests.providers.record_fixtures

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

from providers import stadia  # noqa: E402
from providers.errors import NoRouteError  # noqa: E402
from providers.routing import plan_routes  # noqa: E402
from tests.providers.replay import FIXTURES, request_signature  # noqa: E402
from tests.providers.scenarios import LOAD_LB, PLACES_SCENARIOS, ROUTE_SCENARIOS  # noqa: E402


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


def record(name: str, run) -> None:
    transport = RecordingTransport()
    client = httpx.Client(base_url=stadia.BASE_URL, timeout=stadia.TIMEOUT_S, transport=transport)
    try:
        run(stadia.StadiaMaps(client, os.environ["STADIA_API_KEY"]))
    except NoRouteError as exc:
        print(f"{name}: NoRouteError({exc})")
    text = json.dumps(transport.recorded, separators=(",", ":"))
    if os.environ["STADIA_API_KEY"] in text:
        sys.exit(f"{name}: the API key leaked into the recording; nothing written")
    (FIXTURES / f"{name}.json").write_text(text + "\n")
    print(f"{name}: {len(transport.recorded)} requests, {len(text) // 1024} KB")


def main() -> None:
    from django.test.utils import override_settings

    # Record from the provider, never from a warm cache.
    with override_settings(
        CACHES={"default": {"BACKEND": "django.core.cache.backends.dummy.DummyCache"}}
    ):
        for name, (origin, destination) in ROUTE_SCENARIOS.items():
            record(name, lambda maps, o=origin, d=destination: plan_routes(maps, o, d, LOAD_LB))
        for name, text in PLACES_SCENARIOS.items():
            record(name, lambda maps, t=text: maps.autocomplete(t))


if __name__ == "__main__":
    main()
