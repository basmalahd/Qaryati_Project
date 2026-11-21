from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GeoLocation:
    latitude: float
    longitude: float
    display_name: str


class GeocodingError(Exception):
    """Base class for everything that can go wrong talking to a geocoding provider."""


class GeocodingUnavailableError(GeocodingError):
    """Temporary failure (timeout, network error, 5xx, 429) that persisted after retries."""


class GeocodingBadResponseError(GeocodingError):
    """The provider rejected the request or returned something we cannot use. Not retried."""


class GeocodingProvider(Protocol):
    """The only thing the rest of the app knows about geocoding.

    Swapping Nominatim for another provider means writing one new class that
    implements `search` - no service or API code changes.
    """

    def search(
        self, query: str, *, limit: int = 5, country_code: str | None = None
    ) -> list[GeoLocation]: ...
