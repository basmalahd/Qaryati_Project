# Engineering decisions register

The course specification leaves internal engineering choices to the team. This table lists each one, what we
chose, and where the reasoning lives. Items marked **Planned** are not done yet and have an owner.

| Decision area | What we chose | Reasoning / where |
|---|---|---|
| Technology stack | FastAPI, SQLAlchemy 2.0 (sync), Alembic, PostgreSQL 16, Docker | ADR-001 |
| Architecture | Layered modular monolith: API -> Services -> Repositories -> Models; external systems behind ports | `docs/architecture.md`, ADR-001 |
| Module boundaries | One router, service and repository per concern; one generic child service for village-owned content | ADR-008, developer guide |
| DTOs, validation, mapping | Pydantic schemas per resource (request/response separate from ORM models); validation at the edge, business rules in services | `app/schemas`, developer guide |
| Error responses | One unified error shape with `traceId`; typed `AppError` subclasses translated by global handlers | ADR-003 |
| Transactions | One public service method = one transaction; the service commits once, so a change and its audit entry are atomic | ADR-004 |
| Data conflicts / provenance | Conflicting population values are kept (not overwritten); mandatory source; verification workflow | ADR-005 |
| Audit trail | Single `audit_logs` table with before/after JSON, written in the same transaction | ADR-004 |
| Names and geography | Alternative names and nearby places as separate tables | ADR-007 |
| External API | Geocoding behind a port with timeout, retries, throttling to the provider limit, TTL cache and graceful failure | ADR-006 |
| Authentication / authorization | JWT access (15 min) + refresh (7 days), Argon2id hashing, four roles via `require_roles` | ADR-002 |
| Raw SQL | Two native-SQL cases, both read-only and fully parameterised: villages-by-governorate aggregation (`village_repository.count_by_governorate`) and latest population per village using a window function (`population_repository.latest_per_village`); ORM everywhere else | `app/repositories` |
| Testing | Unit tests with fakes (no DB/network) + integration tests over HTTP; coverage gate 90% | ADR-009, `docs/testing-strategy.md` |
| Git workflow | Feature branches, PRs, reviewer rotation, focused commits | `CONTRIBUTING.md` |
| Configuration | `pydantic-settings` from environment/`.env`; secrets never committed; JWT secret must be 32+ chars | `.env.example` |
| Rate limiting (API) | **Planned** (Shaymaa) | ADR-010 reserved |
| Structured logging | **Planned** (Shaymaa) | ADR-011 reserved |
| CORS, environment configs, CI, Docker production setup | **Planned** (Shaymaa) | - |
| Database indexing and caching of reads | **Planned** (Hanaa), based on k6 measurements | ADR-012 reserved |
| Load testing and performance report | **Planned** (Hanaa) | `docs/performance.md` |
