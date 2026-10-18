"""Cache raw provider responses without letting the cache take the app down (routing D7)."""

import hashlib
import json
import logging
from collections.abc import Callable
from typing import Any

from django.core.cache import cache

from providers.errors import ProviderError

log = logging.getLogger(__name__)


def request_key(namespace: str, payload: Any) -> str:
    """A stable key for a provider request. Payloads must not contain secrets."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"{namespace}:{hashlib.sha256(canonical.encode()).hexdigest()}"


def fetch_cached[T](key: str, ttl_s: int, fetch: Callable[[], T]) -> T:
    """Return the cached value for `key`, or call `fetch` and cache its result.

    Any cache failure is logged and treated as a miss: a Redis outage costs latency, never a
    failed request (stack D3). Exceptions from `fetch` propagate and nothing is cached.
    """
    try:
        hit = cache.get(key)
    except Exception:
        log.warning("cache read failed for %s; calling the provider", key, exc_info=True)
        hit = None
    if hit is not None:
        return hit
    value = fetch()
    try:
        cache.set(key, value, ttl_s)
    except Exception:
        log.warning("cache write failed for %s", key, exc_info=True)
    return value


def fetch_many_cached[T](
    keys: dict[str, Any],
    ttl_s: int,
    fetch: Callable[[list[Any]], dict[Any, T]],
    batch_size: int,
) -> dict[Any, T]:
    """Like `fetch_cached` for many items at once: `keys` maps cache key to item.

    Items missing from the cache go to `fetch` in batches of `batch_size`, and each batch is cached
    as soon as it returns, so a failure part-way keeps the batches already paid for (weather D4).
    `fetch` must return a value for every item it was given. Cache failures are logged and treated
    as misses (stack D3).
    """
    try:
        hits = cache.get_many(list(keys))
    except Exception:
        log.warning("cache read failed for %d keys; calling the provider", len(keys), exc_info=True)
        hits = {}
    found = {keys[key]: value for key, value in hits.items() if key in keys}
    missing = [(key, item) for key, item in keys.items() if key not in hits]
    for i in range(0, len(missing), batch_size):
        batch = missing[i : i + batch_size]
        fetched = fetch([item for _, item in batch])
        if fetched.keys() != {item for _, item in batch}:
            raise ProviderError("The provider answered for different items than were asked.")
        found.update(fetched)
        try:
            cache.set_many({key: fetched[item] for key, item in batch}, ttl_s)
        except Exception:
            log.warning("cache write failed for %d keys", len(batch), exc_info=True)
    return found
