# ADR-010: Per-IP API Rate Limiting

**Status:** Accepted
## Context

Qaryati needs to limit accidental overload and repeated login/register attempts. API errors already have a common response shape and request trace ID.

## Decision
Use a 60-second per-IP, per-category in-memory fixed window, with separate buckets for login (5/min), register (3/min), and other API requests (120/min). Return HTTP 429, `Retry-After` (seconds), and the existing common error JSON (`RATE_LIMITED`). Disable with `RATE_LIMIT_ENABLED=false` for controlled load tests. Do not trust client-supplied forwarded IP headers. Exempt OPTIONS preflight requests.

## Consequences
Simple, dependency-free and testable, but counters are **per Python process** and reset on restart; this does not enforce a shared quota across workers or replicas. Fixed windows allow bursts around boundaries. For multi-instance production, use a shared Redis-backed limiter and configure trusted reverse-proxy client IP handling. These limits are starting defaults and should be tuned from traffic data.
