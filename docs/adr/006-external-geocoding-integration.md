# ADR-006: External geocoding integration

## Status
Accepted

## Context
The project requires at least one external API that improves village data, integrated
robustly: timeouts and failures must not crash the system, retries and rate limits must be
considered, caching used when useful, and the provider must be replaceable.

## Decision
- **Provider:** Nominatim (OpenStreetMap): free, no API key (no secret to leak), good coverage
  of place names. Restricted to `countrycodes=ps`.
- **Port & adapter:** the app depends only on the `GeocodingProvider` protocol
  (`search(query, limit, country_code) -> list[GeoLocation]`). `NominatimGeocoder` is one
  adapter; `CachingGeocoder` is a decorator. Switching provider = one new class + one line
  in `build_geocoder`.
- **Timeouts:** 5 s total, 2 s connect.
- **Retries:** timeouts, network errors, HTTP 429 and 5xx are retried (max 2 retries) with
  exponential backoff 0.5 s, 1 s (capped at 5 s) and a small `Retry-After` is honoured.
  4xx responses are **not** retried: repeating an invalid request cannot succeed.
- **Rate limit:** calls are serialized and spaced >= 1.1 s (provider policy is 1 req/s) and
  requests carry an identifying `User-Agent`.
- **Cache:** in-memory TTL cache (24 h for hits, 1 h for empty results, 1000 entries, query
  normalised). **Failures are never cached.** The `TTLCache` interface (get/set) lets Redis
  replace it when running several instances.
- **Failure mapping:** exhausted retries -> `503 GEOCODING_UNAVAILABLE`; unusable response ->
  `502 GEOCODING_BAD_RESPONSE`, both in the standard error format with no internal details.
  The rest of the API is unaffected.
- **No silent overwrite:** `GET /villages/{id}/location-suggestions` only *suggests*
  candidates (with distance from the current coordinates). A human applies one through the
  normal audited `PATCH /villages/{id}`.
- Access limited to `editor`/`admin` so the shared provider quota can't be burned by anyone.

## Consequences
+ Provider outages degrade one feature only; behaviour is covered by offline tests
  (mock transport, fake clock), no real network needed in CI.
+ Replaceable provider, bounded outbound traffic, no secrets.
- The in-memory cache and throttle are per process (fine for one instance).
- Retries/throttle use blocking sleeps in a worker thread; acceptable at this scale,
  an async client would be the next step under heavy load.
- A public Nominatim instance has no SLA; production use should self-host or use a paid provider.
