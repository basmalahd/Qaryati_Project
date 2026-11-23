from app.core.cache import MISSING, TTLCache
from app.core.geo import haversine_km


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def test_entries_expire():
    clock = FakeClock()
    cache = TTLCache(clock=clock)
    cache.set("k", "v", ttl_seconds=10)
    assert cache.get("k") == "v"
    clock.now = 9.9
    assert cache.get("k") == "v"
    clock.now = 10
    assert cache.get("k") is MISSING


def test_none_is_a_valid_cached_value():
    cache = TTLCache()
    cache.set("k", None, ttl_seconds=10)
    assert cache.get("k") is None
    assert cache.get("other") is MISSING


def test_oldest_entry_is_evicted_when_full():
    cache = TTLCache(max_size=2)
    cache.set("a", 1, 100)
    cache.set("b", 2, 100)
    cache.set("c", 3, 100)
    assert cache.get("a") is MISSING
    assert cache.get("b") == 2 and cache.get("c") == 3 and len(cache) == 2


def test_haversine():
    assert haversine_km(32.0, 35.0, 32.0, 35.0) == 0
    assert abs(haversine_km(32.0, 35.0, 33.0, 35.0) - 111.2) < 0.5  # 1 degree of latitude
