import pytest

from providers import cache as provider_cache
from providers.cache import fetch_cached, fetch_many_cached, request_key
from providers.errors import ProviderError


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


def test_fetch_many_asks_the_provider_only_for_misses():
    asked = []

    def fetch(items):
        asked.append(list(items))
        return {item: item * 10 for item in items}

    assert fetch_many_cached({"a": 1, "b": 2}, 60, fetch, 10) == {1: 10, 2: 20}
    assert fetch_many_cached({"a": 1, "b": 2, "c": 3}, 60, fetch, 10) == {1: 10, 2: 20, 3: 30}
    assert asked == [[1, 2], [3]]


def test_fetch_many_keeps_the_batches_before_a_failure():
    asked = []

    def fails_on_the_second_batch(items):
        asked.append(list(items))
        if len(asked) == 2:
            raise ProviderError("rate limited")
        return {item: item for item in items}

    keys = {"a": 1, "b": 2, "c": 3}
    with pytest.raises(ProviderError):
        fetch_many_cached(keys, 60, fails_on_the_second_batch, 2)
    assert fetch_many_cached(keys, 60, fails_on_the_second_batch, 2) == {1: 1, 2: 2, 3: 3}
    assert asked == [[1, 2], [3], [3]]


@pytest.mark.parametrize(
    "answer", [{1: "x"}, {1: "x", 2: "y", 3: "z"}], ids=["too_few", "too_many"]
)
def test_fetch_many_refuses_an_answer_for_other_items(answer):
    with pytest.raises(ProviderError, match="different items"):
        fetch_many_cached({"a": 1, "b": 2}, 60, lambda items: answer, 10)
    assert fetch_many_cached({"a": 1, "b": 2}, 60, lambda items: {1: 1, 2: 2}, 10) == {1: 1, 2: 2}


def test_fetch_many_with_everything_cached_makes_no_call():
    fetch_many_cached({"a": 1}, 60, lambda items: {i: i for i in items}, 10)

    def must_not_call(items):
        raise AssertionError("provider called for cached items")

    assert fetch_many_cached({"a": 1}, 60, must_not_call, 10) == {1: 1}


class BrokenManyCache(BrokenCache):
    def get_many(self, keys):
        raise ConnectionError("redis is down")

    def set_many(self, data, timeout):
        raise ConnectionError("redis is down")


def test_fetch_many_survives_a_cache_outage(monkeypatch, caplog):
    monkeypatch.setattr(provider_cache, "cache", BrokenManyCache())
    fresh = fetch_many_cached({"a": 1}, 60, lambda items: {i: "fresh" for i in items}, 10)
    assert fresh == {1: "fresh"}
    assert "cache read failed" in caplog.text
    assert "cache write failed" in caplog.text
