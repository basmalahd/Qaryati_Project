# ADR-011: Structured JSON Request Logging

**Status:** Proposed — pending team review

## Context
Qaryati needs searchable, consistent request diagnostics correlated with its `X-Request-ID` error trace IDs.

## Decision
Emit one JSON access log per request with UTC timestamp, level, logger, request ID, HTTP method, path (without query string), status, and elapsed milliseconds. Configure log level via `LOG_LEVEL` (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). Do not include Authorization headers, cookies, request or response bodies, query parameters, passwords, or tokens. Preserve existing log handlers; install a managed JSON handler once.

## Consequences
Access logs can be indexed and correlated with error responses. Request paths may still contain sensitive path parameters; routes with such parameters should be normalized to route templates or redacted before production. Existing third-party loggers and exception handlers may log unredacted data: they require separate audit and centralized redaction policy. Log retention/access control should be configured by deployment operators.
