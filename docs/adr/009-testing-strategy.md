# ADR-009: Testing strategy

## Status
Accepted

## Context
The project asks for a testing structure, test-data strategy, mocking decisions and a division
between unit and integration tests. The suite must be fast enough to run before every commit
and reliable enough to run in CI.

## Decision
- Two folders decide the level and the marker: `tests/unit` (fakes, no DB, no network) and
  `tests/integration` (real app + in-memory SQLite). `conftest.py` rejects tests outside both.
- Services are unit-tested against fake repositories and a fake session, asserting rules and the
  order `insert -> audit -> commit`. The HTTP contract, SQL and constraints are tested end to end.
- The database is **not** mocked in integration tests; external providers are replaced through
  dependency overrides or `httpx.MockTransport`; time is faked. Tests never use the real network.
- SQLite (foreign keys on) for speed locally; the same suite runs against PostgreSQL in CI.
- Coverage is measured with branch coverage and gated at 90%.

## Consequences
+ Fast feedback (`pytest -m unit` in seconds) and independent, order-free tests.
+ Layer wiring and database constraints are really exercised.
- SQLite is not PostgreSQL: dialect differences can slip through locally; CI on PostgreSQL and
  manual migration checks on the real container are the safety nets.
- Faking repositories couples unit tests to the services' collaborators; acceptable because the
  integration level catches real wiring errors.
