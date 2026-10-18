import httpx
import pytest
from django.core.cache import cache
from django.test import Client

from providers import stadia
from providers.errors import ProviderError
from tests.providers.replay import replay_client


@pytest.fixture(autouse=True)
def empty_cache():
    cache.clear()


@pytest.fixture
def recorded_places(monkeypatch):
    maps = stadia.StadiaMaps(replay_client("stadia_places_denv", stadia.BASE_URL), "test-key")
    monkeypatch.setattr(stadia, "default", lambda: maps)


def test_places_returns_label_and_coordinates(recorded_places):
    response = Client().get("/api/places", {"q": "Denv"})
    assert response.status_code == 200
    first = response.json()[0]
    assert first["label"] == "Denver, CO, USA"
    assert first["lat"] == pytest.approx(39.74, abs=0.05)
    assert first["lon"] == pytest.approx(-104.99, abs=0.05)


@pytest.mark.parametrize("q", ["", "D", "x" * 101])
def test_places_rejects_queries_outside_2_to_100_chars(q):
    assert Client().get("/api/places", {"q": q}).status_code == 400


def test_provider_failure_is_a_502_with_a_reason(monkeypatch):
    def failing():
        raise ProviderError("The routing provider could not be reached.")

    monkeypatch.setattr(stadia, "default", failing)
    response = Client().get("/api/places", {"q": "Denv"})
    assert response.status_code == 502
    assert response.json() == {"detail": "The routing provider could not be reached."}


def test_the_key_never_reaches_the_response(monkeypatch):
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return replay_client("stadia_places_denv", stadia.BASE_URL).send(request)

    client = httpx.Client(base_url=stadia.BASE_URL, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(stadia, "default", lambda: stadia.StadiaMaps(client, "secret-key"))
    response = Client().get("/api/places", {"q": "Denv"})
    assert "secret-key" in seen[0]
    assert b"secret-key" not in response.content


def test_invalid_input_has_the_same_error_shape_as_other_failures():
    body = Client().get("/api/places", {"q": "D"}).json()
    assert body["detail"] == "q: Ensure this field has at least 2 characters."
    assert body["fields"] == {"q": ["Ensure this field has at least 2 characters."]}
