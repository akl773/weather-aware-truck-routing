import pytest
from django.core.cache import cache

from providers import cache as provider_cache
from providers.cache import fetch_cached, request_key


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


def test_second_fetch_is_served_from_the_cache():
    calls = []

    def fetch():
        calls.append(1)
        return {"ok": True}

    assert fetch_cached("k", 60, fetch) == {"ok": True}
    assert fetch_cached("k", 60, fetch) == {"ok": True}
    assert len(calls) == 1


def test_provider_errors_are_not_cached():
    def failing():
        raise RuntimeError("provider down")

    with pytest.raises(RuntimeError):
        fetch_cached("k", 60, failing)
    assert fetch_cached("k", 60, lambda: "fresh") == "fresh"


class BrokenCache:
    def get(self, key):
        raise ConnectionError("redis is down")

    def set(self, key, value, timeout):
        raise ConnectionError("redis is down")


def test_cache_outage_falls_through_to_the_provider(monkeypatch, caplog):
    monkeypatch.setattr(provider_cache, "cache", BrokenCache())
    assert fetch_cached("k", 60, lambda: "from provider") == "from provider"
    assert "cache read failed" in caplog.text
    assert "cache write failed" in caplog.text


def test_request_key_ignores_key_order():
    assert request_key("ns", {"a": 1, "b": 2}) == request_key("ns", {"b": 2, "a": 1})
    assert request_key("ns", {"a": 1}) != request_key("other", {"a": 1})
