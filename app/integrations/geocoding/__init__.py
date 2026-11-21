import httpx

from app.core.cache import TTLCache
from app.core.config import Settings
from app.integrations.geocoding.base import (
    GeocodingBadResponseError, GeocodingError, GeocodingProvider, GeocodingUnavailableError,
    GeoLocation,
)
from app.integrations.geocoding.caching import CachingGeocoder
from app.integrations.geocoding.nominatim import NominatimGeocoder

__all__ = [
    "GeocodingBadResponseError", "GeocodingError", "GeocodingProvider",
    "GeocodingUnavailableError", "GeoLocation", "build_geocoder",
]


def build_geocoder(settings: Settings) -> GeocodingProvider:
    """Composition root for the geocoding stack: Nominatim adapter wrapped in a cache."""
    client = httpx.Client(
        base_url=settings.geocoding_base_url,
        headers={"User-Agent": settings.geocoding_user_agent, "Accept": "application/json"},
        timeout=httpx.Timeout(settings.geocoding_timeout_seconds, connect=2.0),
    )
    provider = NominatimGeocoder(
        client,
        max_retries=settings.geocoding_max_retries,
        min_interval=settings.geocoding_min_interval_seconds,
    )
    return CachingGeocoder(
        provider,
        TTLCache(max_size=settings.geocoding_cache_max_entries),
        ttl=settings.geocoding_cache_ttl_seconds,
        empty_ttl=settings.geocoding_empty_cache_ttl_seconds,
    )
