import logging

from app.core.cache import MISSING, TTLCache
from app.integrations.geocoding.base import GeocodingProvider, GeoLocation

logger = logging.getLogger("app.integrations.geocoding")


class CachingGeocoder:
    """Decorator that caches any GeocodingProvider.

    - successful lookups are cached for a long time (place coordinates barely change);
    - *empty* results are cached for a shorter time (don't hammer the provider for typos);
    - failures are never cached, so recovery is immediate once the provider is back.
    """

    def __init__(self, inner: GeocodingProvider, cache: TTLCache, ttl: int, empty_ttl: int):
        self._inner = inner
        self._cache = cache
        self._ttl = ttl
        self._empty_ttl = empty_ttl

    def search(
        self, query: str, *, limit: int = 5, country_code: str | None = None
    ) -> list[GeoLocation]:
        key = (" ".join(query.lower().split()), limit, country_code)
        cached = self._cache.get(key)
        if cached is not MISSING:
            logger.debug("geocoding cache hit")
            return list(cached)

        results = self._inner.search(query, limit=limit, country_code=country_code)
        self._cache.set(key, tuple(results), self._ttl if results else self._empty_ttl)
        return results
