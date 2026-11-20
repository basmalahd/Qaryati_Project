# ADR-003: Unified error response format

## Status
Accepted

## Context
Clients and tests need one predictable error shape across the whole API.

## Decision
Every error (business, validation, auth, unknown route, unexpected) returns:

```json
{
  "timestamp": "2026-11-20T16:00:00+00:00",
  "status": 409,
  "code": "CONFLICT",
  "message": "A user with this email already exists",
  "details": [{"field": "email", "message": "..."}],
  "traceId": "9f1c..."
}
```

Services raise typed `AppError` subclasses (no HTTP knowledge in business logic);
global handlers translate them. Unexpected errors return a generic 500 and the
details are logged server-side only. `traceId` is the `X-Request-ID` (client-supplied
or generated) and is echoed in the response header for log correlation.

## Consequences
+ One format to document and test; no internals leak to clients.
+ Business layer stays independent of the web framework.
- Every new error type must subclass `AppError` to get the format.
