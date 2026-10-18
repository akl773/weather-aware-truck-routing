import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def empty_cache():
    """Every test starts cold, so a cached response never hides a missing recording."""
    cache.clear()
    yield
    cache.clear()
