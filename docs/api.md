# API Guide

Base URL: `http://localhost:8000/api/v1` · Interactive docs: `/docs` (Swagger) · Machine-readable spec:
[`docs/api/openapi.json`](api/openapi.json) · Postman: [`docs/api/qaryati.postman_collection.json`](api/qaryati.postman_collection.json)

## 1. Conventions
| Topic | Rule |
|---|---|
| Versioning | URI prefix `/api/v1`. A breaking change would ship as `/api/v2` next to v1. |
| Resources | Plural nouns; village-owned data is nested: `/villages/{village_id}/population`. |
| Methods | `GET` read, `POST` create (201), `PATCH` partial update (200), `DELETE` remove (204). |
| Lists | Paginated, filterable and sortable where relevant (see section 4). |
| Format | JSON only. Field names are `snake_case`. |
| Tracing | Every response carries `X-Request-ID` (echoes the client's header or generates one). |

## 2. Authentication flow
1. **Register (optional):** `POST /auth/register` with `email`, `password` (8-128 chars), `full_name`.
   Always creates a `viewer`. Only an admin can change roles (`PATCH /users/{user_id}/role`).
2. **Login:** `POST /auth/login` with `email` and `password`. Response:
   ```json
   {"access_token": "...", "refresh_token": "...", "token_type": "bearer", "expires_in": 900}
   ```
3. **Call the API:** send `Authorization: Bearer <access_token>` on every endpoint except
   `/health`, `/auth/register`, `/auth/login`, `/auth/refresh`.
4. **Refresh:** when the access token expires (15 min), `POST /auth/refresh` with `{"refresh_token": "..."}`
   returns a new pair. Refresh tokens last 7 days; a refresh token cannot be used as an access token.
5. **First admin:** created with the CLI script (`python -m app.scripts.create_admin`), never through a public endpoint.

Design rationale: [ADR-002](adr/002-authentication.md).

## 3. Authorization (roles)
| Action | viewer | verifier | editor | admin |
|---|---|---|---|---|
| Read any data | yes | yes | yes | yes |
| Create / update villages, names, nearby places, sources, population values, history, landmarks, heritage, economy, facilities | | | yes | yes |
| Change a population record's verification status | | yes | | yes |
| Delete anything, create governorates, read audit log, change user roles | | | | yes |
| Geocoding endpoints | | | yes | yes |

`401` = missing/invalid/expired token. `403` = valid token, role not allowed.

## 4. Lists: pagination, filtering, sorting
`GET /villages?q=&governorate_id=&sort=name_ar|name_en|created_at|id&order=asc|desc&page=1&page_size=20`
```json
{"items": [], "page": 1, "page_size": 20, "total": 0, "total_pages": 0}
```
Nested lists accept their own filters, e.g. `/villages/{id}/population?verification_status=&from_year=&to_year=`,
`/events?from_year=&to_year=`, `/landmarks?category=`, `/facilities?facility_type=`.

### Statistics (native SQL)
- `GET /stats/villages-by-governorate`: number of villages per governorate.
- `GET /stats/latest-population?governorate_id=&limit=20`: the most recent usable population record of each village,
  largest first. Newest year wins; on the same year `verified` beats `pending`; `disputed` records are ignored and
  villages without a usable record are not listed. `limit` is 1-100.

## 5. Error model
Every error (business, validation, auth, unknown route, unexpected) has the same shape ([ADR-003](adr/003-error-model.md)):
```json
{
  "timestamp": "2026-11-25T10:00:00+00:00",
  "status": 422,
  "code": "VALIDATION_ERROR",
  "message": "Request validation failed",
  "details": [{"field": "email", "message": "value is not a valid email address"}],
  "traceId": "9f1c..."
}
```
| Status | `code` | When |
|---|---|---|
| 401 | `UNAUTHORIZED` | Missing, invalid or expired token; wrong credentials |
| 403 | `FORBIDDEN` | Role not allowed |
| 404 | `NOT_FOUND` | Unknown resource or route |
| 405 | `METHOD_NOT_ALLOWED` | Wrong HTTP method |
| 409 | `CONFLICT` | Duplicate (e.g. same village/year/source population record) |
| 422 | `VALIDATION_ERROR` / `UNPROCESSABLE` | Invalid body/params, or a business rule is violated |
| 502 / 503 | `BAD_GATEWAY` / `SERVICE_UNAVAILABLE` | External geocoding provider failed or timed out |
| 500 | `INTERNAL_ERROR` | Unexpected; details only in server logs, use `traceId` to find them |

## 6. Data quality rules visible in the API
- Population records require a `source_id`, and different sources may disagree for the same year: both are kept and reads expose `has_conflict` ([ADR-005](adr/005-population-records.md)).
- Verification flow `pending -> verified | disputed`; verified records are locked until a verifier marks them `disputed`.
- History, landmarks, heritage, economy and facilities can cite a `source_id`.
- Every create/update/delete is recorded in the audit log (`GET /audit-logs`, admin only) with who, when and before/after values ([ADR-004](adr/004-audit-and-change-history.md)).
- Geocoding returns *suggestions* only; nothing is written until an editor applies it with `PATCH /villages/{id}` ([ADR-006](adr/006-external-geocoding-integration.md)).

## 7. Try it
```bash
curl -s -X POST localhost:8000/api/v1/auth/login -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"..."}'
curl -s localhost:8000/api/v1/villages?q=nablus -H "Authorization: Bearer $TOKEN"
```
In Postman: import the collection, run **auth > POST /api/v1/auth/login** once (it stores the token), then any request.
