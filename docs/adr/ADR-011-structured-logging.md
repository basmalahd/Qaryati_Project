# ADR-011: Structured JSON Request Logging

**Status:** Accepted

## Context
Qaryati needs searchable, consistent request diagnostics correlated with its `X-Request-ID` error trace IDs.

## Decision
Emit one JSON access log per request with UTC timestamp, level, logger, request ID, HTTP method, path (without query string), status, and elapsed milliseconds. Configure log level via `LOG_LEVEL` (`DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`). Do not include Authorization headers, cookies, request or response bodies, query parameters, passwords, or tokens. Preserve existing log handlers; install a managed JSON handler once.

## Consequences
Access logs can be indexed and correlated with error responses. Sensitive path
parameters must be normalized to route templates or redacted before logging.
Exception logs and third-party logger output require a separate audit and
centralized redaction policy to prevent exposure of passwords, tokens, personal
data, or other sensitive information. Log retention and access control must be
configured by deployment operators.
