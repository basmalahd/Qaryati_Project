import logging
import threading
import time
from typing import Callable

import httpx

from app.integrations.geocoding.base import (
    GeocodingBadResponseError, GeocodingUnavailableError, GeoLocation,
)

logger = logging.getLogger("app.integrations.geocoding")

MAX_BACKOFF_SECONDS = 5.0


class NominatimGeocoder:
    """Adapter for the Nominatim (OpenStreetMap) search API.

    Failure handling:
    - every request has a timeout (configured on the injected httpx client);
    - timeouts, network errors, HTTP 429 and 5xx are retried with exponential backoff
      (honouring a small Retry-After); 4xx are NOT retried: repeating a bad request is pointless;
    - after the retries are exhausted -> GeocodingUnavailableError (callers degrade gracefully);
    - unusable payloads -> GeocodingBadResponseError;
    - calls are spaced by `min_interval` seconds to respect the provider's 1 request/second policy.
    """

    def __init__(
        self,
        client: httpx.Client,
        *,
        max_retries: int = 2,
        backoff_base: float = 0.5,
        min_interval: float = 1.1,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self._client = client
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._min_interval = min_interval
        self._sleep = sleep
        self._clock = clock
        self._lock = threading.Lock()
        self._last_call: float | None = None

    def search(
        self, query: str, *, limit: int = 5, country_code: str | None = None
    ) -> list[GeoLocation]:
        params = {"q": query, "format": "jsonv2", "limit": limit}
        if country_code:
            params["countrycodes"] = country_code

        last_problem = "unknown"
        for attempt in range(self._max_retries + 1):
            self._throttle()
            retry_after: float | None = None
            try:
                response = self._client.get("/search", params=params)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_problem = f"{type(exc).__name__}"
            else:
                if response.status_code == 200:
                    return self._parse(response)
                if response.status_code == 429 or response.status_code >= 500:
                    last_problem = f"HTTP {response.status_code}"
                    retry_after = self._retry_after(response)
                else:
                    logger.warning("Geocoding provider rejected request: HTTP %s", response.status_code)
                    raise GeocodingBadResponseError(f"Provider answered HTTP {response.status_code}")

            if attempt < self._max_retries:
                delay = retry_after if retry_after is not None else min(
                    self._backoff_base * (2**attempt), MAX_BACKOFF_SECONDS
                )
                logger.warning(
                    "Geocoding attempt %d/%d failed (%s); retrying in %.1fs",
                    attempt + 1, self._max_retries + 1, last_problem, delay,
                )
                self._sleep(delay)

        logger.error("Geocoding gave up after %d attempts (%s)", self._max_retries + 1, last_problem)
        raise GeocodingUnavailableError(last_problem)

    # ---- internals ---------------------------------------------------
    def _throttle(self) -> None:
        with self._lock:
            now = self._clock()
            if self._last_call is not None:
                wait = self._min_interval - (now - self._last_call)
                if wait > 0:
                    self._sleep(wait)
                    now = self._clock()
            self._last_call = now

    @staticmethod
    def _retry_after(response: httpx.Response) -> float | None:
        raw = response.headers.get("Retry-After")
        try:
            return min(max(float(raw), 0.0), MAX_BACKOFF_SECONDS) if raw is not None else None
        except ValueError:  # HTTP-date form: ignore and use normal backoff
            return None

    @staticmethod
    def _parse(response: httpx.Response) -> list[GeoLocation]:
        try:
            data = response.json()
        except ValueError:
            raise GeocodingBadResponseError("Provider returned invalid JSON")
        if not isinstance(data, list):
            raise GeocodingBadResponseError("Provider returned an unexpected payload")

        results: list[GeoLocation] = []
        for item in data:
            try:
                lat, lon = float(item["lat"]), float(item["lon"])
                name = str(item.get("display_name", ""))
            except (KeyError, TypeError, ValueError, AttributeError):
                logger.warning("Skipping malformed geocoding result")
                continue
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                results.append(GeoLocation(lat, lon, name))
        return results
