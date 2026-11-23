# Qaryati - Palestinian Villages Knowledge Platform

## Run
```bash
cp .env.example .env
docker compose up --build
```
- Swagger: http://localhost:8000/docs
- Health:  http://localhost:8000/api/v1/health

## Test
```bash
pip install -r requirements.txt
pytest
```

## Database migrations
```bash
docker compose exec api alembic upgrade head      # apply
docker compose exec api alembic downgrade -1      # rollback one step
docker compose exec api alembic revision --autogenerate -m "message"
```

## Authentication
1. Put a strong secret in `.env` (`JWT_SECRET_KEY`, 32+ chars):
   `docker run --rm python:3.12-slim python -c "import secrets;print(secrets.token_hex(32))"`
2. Apply migrations: `docker compose exec api alembic upgrade head`
3. Create the first admin:
   `docker compose exec api python -m app.scripts.create_admin --email you@example.com --name "Your Name"`
4. In Swagger (`/docs`): `POST /api/v1/auth/login`, then **Authorize** with the access token.

Roles: `admin`, `editor`, `verifier`, `viewer` (public registration creates `viewer`).

## Permissions
| Action | viewer | verifier | editor | admin |
|---|---|---|---|---|
| Read villages / governorates / stats | yes | yes | yes | yes |
| Create / update villages | | | yes | yes |
| Delete villages | | | | yes |
| Create governorates | | | | yes |
| Read audit log | | | | yes |

## Villages API
`GET /api/v1/villages?q=&governorate_id=&sort=name_ar|name_en|created_at|id&order=asc|desc&page=1&page_size=20`

## Sources & population
| Action | viewer | verifier | editor | admin |
|---|---|---|---|---|
| Read sources / population history | yes | yes | yes | yes |
| Create / update sources | | | yes | yes |
| Add / edit population records | | | yes | yes |
| Change verification status | | yes | | yes |
| Delete population records | | | | yes |

`GET /api/v1/villages/{id}/population?verification_status=&from_year=&to_year=`

## External API: geocoding (Nominatim / OpenStreetMap)
- `GET /api/v1/villages/{id}/location-suggestions` - suggested coordinates for a village (editor/admin)
- `GET /api/v1/geocoding/search?q=Nablus&limit=5` - free-text place search (editor/admin)

Suggestions are never written automatically; apply one with `PATCH /api/v1/villages/{id}`.
Provider settings (all optional): `GEOCODING_BASE_URL`, `GEOCODING_USER_AGENT`,
`GEOCODING_TIMEOUT_SECONDS`, `GEOCODING_MAX_RETRIES`. Design: `docs/adr/006-external-geocoding-integration.md`.

## Names, relations and geography
| Action | viewer | verifier | editor | admin |
|---|---|---|---|---|
| Read names / nearby places | yes | yes | yes | yes |
| Add / edit names, add nearby places | | | yes | yes |
| Delete names / nearby places | | | | yes |

- `GET|POST /api/v1/villages/{id}/names`, `PATCH|DELETE .../names/{name_id}`
- `GET|POST /api/v1/villages/{id}/nearby`, `DELETE .../nearby/{relation_id}`
- `elevation_m` and `area_km2` are regular optional fields of `POST|PATCH /api/v1/villages`.

## History, landmarks, heritage, economy, facilities
Under `/api/v1/villages/{id}/`: `events` (timeline, `?from_year=&to_year=`), `landmarks` (`?category=`),
`heritage` (`?category=`), `economy` (`?category=`), `facilities` (`?facility_type=`).
Each supports `GET`, `POST`, `PATCH /{item_id}` and `DELETE /{item_id}`; every item can cite a `source_id`.

| Action | viewer | verifier | editor | admin |
|---|---|---|---|---|
| Read | yes | yes | yes | yes |
| Create / update | | | yes | yes |
| Delete | | | | yes |

## Testing
```
pip install -r requirements.txt
pytest -m unit          # fast, no DB, no network
pytest -m integration   # HTTP API + in-memory SQLite
pytest --cov=app        # everything + coverage gate (>= 90%)
```
Strategy and trade-offs: [docs/testing-strategy.md](docs/testing-strategy.md) (ADR-009).
Developer conventions: [docs/developer-guide.md](docs/developer-guide.md).
