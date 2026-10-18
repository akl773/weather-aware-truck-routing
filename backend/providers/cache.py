"""Cache raw provider responses without letting the cache take the app down (routing D7)."""

import hashlib
import json
import logging
from collections.abc import Callable
from typing import Any

from django.core.cache import cache

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
