# Developer guide

How the codebase is organised, the conventions every change must follow, and how to run, test
and extend it. Read this together with `docs/architecture.md`, `docs/erd.md` and `docs/adr/`.

## Stack
FastAPI, SQLAlchemy 2.0 (sync), Alembic, PostgreSQL 16, Pydantic v2, PyJWT + Argon2, httpx, pytest. Docker for the app and DB.

## Run and test
```
cp .env.example .env            # then set JWT_SECRET_KEY (32+ chars)
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.create_admin --email you@example.com --name "Your Name"
```
Swagger: http://localhost:8000/docs

Tests need no Postgres and no `.env` (`tests/conftest.py` sets SQLite and a test JWT key):
```
pip install -r requirements.txt
pytest -q
```
Docker mounts only `./app` and `./alembic`; after changing `requirements.txt` or the Dockerfile run `docker compose up --build -d`.

## Layers (dependencies point one way)
`API (app/api) -> services (app/services) -> repositories (app/repositories) -> models (app/models)`

| Layer | Does | Must not |
|---|---|---|
| Router (`app/api/v1/*.py`) | HTTP, DTO validation, auth (`get_current_user`, `require_roles`), calls one service method | contain rules or queries |
| Service | Business rules, **one public method = one transaction (the service commits)**, writes the audit entry, raises `AppError` subclasses | know about HTTP, return `Response` objects |
| Repository | Queries (ORM, one native-SQL case), eager loading, pagination, `flush()` only | commit, decide rules |
| Integration (`app/integrations`) | External providers behind a port (see ADR-006) | leak provider details upward |
| Schemas (`app/schemas`) | Pydantic request/response DTOs | depend on services |

## Conventions
- **Errors:** raise `NotFoundError`, `ConflictError`, `UnprocessableError`, `ForbiddenError`, `UnauthorizedError`, `ServiceUnavailableError`, `BadGatewayError` from `app/core/errors.py`. Global handlers produce the unified body `{timestamp, status, code, message, details, traceId}` (ADR-003). Never return ad-hoc error JSON.
- **Validation:** shape/range checks in Pydantic schemas (`Annotated` types); cross-entity rules (exists, duplicate, workflow) in services.
- **PATCH:** partial update with `data.model_dump(exclude_unset=True)`; apply only fields that really changed; a no-op writes nothing and creates no audit entry. Fields that must not be null get a `field_validator`.
- **Audit:** every create/update/delete calls `AuditService.record(actor, action, entity_type, entity_id, {"before"/"after": ...})` **before** the single `commit()`, so data and audit are atomic (ADR-004).
- **Permissions:** `Depends(require_roles(Role.EDITOR, Role.ADMIN))`. Reads need any authenticated user; deletes are admin-only; population status changes are verifier/admin.
- **Lists:** pagination via `Page[...]` and `build_page` (`page`, `page_size <= 100`); sort fields come from a whitelist; user input in LIKE/ILIKE goes through `escape_like`.
- **Village-owned content:** add a model using `VillageChildMixin`, schemas, and a ~10-line subclass of `VillageChildService` (ADR-008). Rules, audit and tests come almost for free.
- **Config:** everything comes from environment variables through `app/core/config.py` (`Settings`). Add new settings there with a safe default and document them in `.env.example`. Never hard-code secrets or URLs.

## Database and migrations
- Migrations are written by hand in `alembic/versions/` (numbered `000N_...`). Model and migration must match: after `alembic upgrade head`, `alembic check` must print `No new upgrade operations detected`.
- Use batch mode (`op.batch_alter_table`) for ALTERs so migrations also run on SQLite.
- Declare floats explicitly as `mapped_column(Float)`; a bare `Mapped[float]` caused a type mismatch in `alembic check`.
- Mirror CHECK constraints in the schemas; tests assert that schema `Literal` values equal the model tuples.
- Verify a migration on SQLite quickly (PowerShell):
  ```
  $env:DATABASE_URL = "sqlite:///./test.db"
  $env:JWT_SECRET_KEY = "k" * 40      # any string of 32+ characters
  alembic upgrade head; alembic check; alembic downgrade base
  ```
  Always also run the migration once on the real PostgreSQL container.

## Testing conventions
- Fixtures in `tests/conftest.py`: `client` (TestClient with an in-memory SQLite DB, foreign keys enforced like PostgreSQL), `session_factory`, and `auth_headers("admin"|"editor"|"verifier"|"viewer")`.
- Shared helpers in `tests/helpers.py` (`make_gov`, `make_village`, `make_source`, `API`).
- External services are replaced with fakes through `app.dependency_overrides` (e.g. `get_geocoder`); **tests never touch the real network**.
- Every endpoint needs tests for: permissions (401/403), validation (422), not-found (404), conflicts (409) and the happy path; writes also check the audit entry.

## Where things are
```
app/api/v1/        routers            app/services/       business rules
app/core/          config, errors,    app/repositories/   data access
                   security, cache    app/integrations/   external providers (ports/adapters)
app/models/        SQLAlchemy tables  app/schemas/        Pydantic DTOs
app/scripts/       CLI scripts        alembic/versions/   migrations
tests/             pytest suite       docs/               ADRs, ERD, architecture
```

## Definition of done for a task
- [ ] Follows the layering and conventions above
- [ ] Tests added and the whole suite passes
- [ ] Migration added and `alembic check` is clean (if the schema changed)
- [ ] Docs/ADR updated if a decision was made
- [ ] PR filled in with What / Why / Tests / Decisions, reviewed by a teammate
