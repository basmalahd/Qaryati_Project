# Testing strategy

Decision record: `docs/adr/009-testing-strategy.md`. Conventions for writing tests: `docs/developer-guide.md`.

## Two levels

| | Unit (`tests/unit`) | Integration (`tests/integration`) |
|---|---|---|
| What runs | One service/function with **fake** repositories and a fake session | The real FastAPI app through `TestClient`, real routers, services, repositories, SQLAlchemy |
| Database | none | in-memory SQLite, created per test, foreign keys enforced |
| Network | none | none (external provider faked) |
| Purpose | Business rules, ordering of effects, edge cases, fast feedback | Wiring: HTTP contract, validation, permissions, error format, SQL, constraints, audit |
| Speed | ~4 s for the whole level | ~80 s |
| Run | `pytest -m unit` | `pytest -m integration` |

The suite is deliberately wider at the integration level: most of the value of this system is in how
layers cooperate (permissions + validation + transaction + audit + constraints), and that is only visible end to end.
Unit tests protect the rules that are cheap to test in isolation and hard to reach through HTTP
(e.g. "a rejected request writes nothing", "the audit entry is recorded before the single commit").

## What is tested
- **Rules of every service:** permissions, validation, conflicts, workflow (verified records are locked), no-op updates write nothing.
- **Transaction boundary:** the service records the audit entry and commits once, in that order (unit), and the entry exists afterwards (integration).
- **API contract:** status codes, unified error body, pagination/sorting limits, 401/403/404/409/422 for every endpoint family.
- **Database integrity:** CHECK/UNIQUE/FK behaviour (e.g. cascade on village delete), and that schema `Literal`s equal the model's allowed values.
- **External integration:** retry/backoff, timeout, rate-limit throttling, caching and failure mapping, with `httpx.MockTransport` and a fake clock (no sleeping, no network).

## Test data
- Each integration test gets a fresh in-memory database (fixture `session_factory`), so tests are independent and can run in any order.
- Data is created through the API itself with small helpers (`tests/helpers.py`) or through `auth_headers(role)`, which creates a user of the wanted role. No shared mutable fixtures, no data files.
- Unit tests build only the objects a rule needs.

## Mocking decisions
| Dependency | Unit | Integration | Why |
|---|---|---|---|
| Database | fake repositories | **real** (SQLite) | Mocking the DB in API tests would hide SQL/constraint bugs |
| Geocoding provider | n/a | fake via `dependency_overrides[get_geocoder]` | No real network, deterministic |
| HTTP client of the adapter | `httpx.MockTransport` | n/a | Exercise retry/timeout logic for real |
| Time / sleep | fake clock | n/a | Test backoff and throttling instantly |

## SQLite in tests vs PostgreSQL in production
**Trade-off.** SQLite makes the suite fast and dependency-free (no container needed to run `pytest`),
but it is a different engine. Mitigations: foreign keys are switched on to behave like PostgreSQL;
migrations are written in batch mode and verified with `alembic upgrade`, `alembic check` and `downgrade`;
PostgreSQL-only features are avoided in application code (the one native SQL query is portable);
and the CI pipeline runs the same suite against a real PostgreSQL service container (planned task S4).

## Coverage
`pytest --cov=app` measures line and branch coverage of `app/` (CLI scripts excluded) and **fails below 90%**
(`.coveragerc`). Current value is about 99%. Coverage is a safety net, not the goal: a line that runs
without an assertion proves nothing, so new tests assert behaviour (status code, body, audit entry, no write).

## Not covered by pytest (on purpose)
- Load and performance: k6 scenarios and the performance report (`docs/performance.md`).
- The real Nominatim service: availability is outside our control; its failure modes are simulated.
