# Qaryati — S5 Production Docker

## Included files
- `Dockerfile.prod`: Python 3.12, non-root runtime user, FastAPI via Uvicorn.
- `compose.prod.yml`: PostgreSQL 16, one-shot Alembic migration, API started only after migration succeeds.
- `.dockerignore`: excludes tests, virtualenv, Git, and secret environment files from build context.
- `.env.prod.example`: template only; **never commit actual `.env.prod`**.

## Important prerequisites
- `requirements.txt`, `app/main.py`, `alembic.ini`, and `alembic/` must exist.
- Check that `alembic/env.py` uses `DATABASE_URL` or the app settings and that migrations work with PostgreSQL.
- Review any existing Docker/Compose configuration before replacing files.
- Configure HTTPS/TLS using a reverse proxy outside this Compose stack.
- In-memory rate limiting is only per process; do not scale API replicas without a shared limiter.

## Local server deployment (Bash)
```bash
cp .env.prod.example .env.prod
# Replace placeholders with real credentials, on the deployment server only.
chmod 600 .env.prod
# Ensure .env.prod is ignored by Git.
docker compose -f compose.prod.yml --env-file .env.prod config --quiet
docker compose -f compose.prod.yml --env-file .env.prod up --build -d
docker compose -f compose.prod.yml --env-file .env.prod ps
docker compose -f compose.prod.yml --env-file .env.prod logs --tail=100 migrate api
docker compose -f compose.prod.yml --env-file .env.prod exec api id
```

## Git hygiene
Add these entries to your existing `.gitignore` (do not replace it):
```gitignore
.env.prod
.env.prod.*
!.env.prod.example
```

## Operational cautions
- The PostgreSQL password is interpolated into a SQLAlchemy URL. If it contains URL-special characters (`@`, `:`, `/`, `%`, etc.), percent-encode them in the database URL or adapt the configuration to construct the URL safely. Compose variable interpolation also treats `$` specially.
- Do not run multiple concurrent migration jobs during deployment.
- Do not publish the database port. The API port is bound to `127.0.0.1` for a local reverse proxy.
- Back up and test restore of PostgreSQL before migrations.
- This package has not been run against the full repository or a Docker daemon; verify it before production use.
