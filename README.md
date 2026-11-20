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
