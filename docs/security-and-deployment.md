# Qaryati — Security and Deployment Guide

## 1. Overview

This document describes the security measures and production deployment process for the Qaryati FastAPI backend.

## 2. Authentication and Password Security

- Passwords should be stored as secure hashes using Argon2.
- JWT signing secrets must be kept confidential.
- JWT expiration settings should be configured appropriately.
- Authentication endpoints are protected by rate limiting.

## 3. Environment Variables and Secrets

Production credentials must be provided through environment variables.

Required production settings include:

- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_DB`
- `JWT_SECRET_KEY`
- `CORS_ORIGINS`

Never commit `.env.prod` or production credentials to Git. Use `.env.prod.example` as a configuration template.

## 4. CORS Protection

Only explicitly trusted frontend origins should be allowed in production. Avoid wildcard origins when credentials are involved.

## 5. Rate Limiting

Qaryati uses application-level rate limiting to reduce abuse of authentication and other endpoints.

The current in-memory implementation is suitable for a single application process. A shared store such as Redis is recommended for deployments with multiple workers or replicas.

## 6. Structured Logging

Application logs should be structured and must not expose passwords, JWT tokens, authorization headers, or other secrets.

Third-party HTTP client logs should also be reviewed to prevent sensitive query parameters from appearing in log messages.

## 7. Production Docker Architecture

The production Compose configuration contains three services:

- `db`: PostgreSQL 16 database.
- `migrate`: one-time Alembic migration service.
- `api`: FastAPI application.

The API starts only after migrations complete successfully.

The API port is bound to `127.0.0.1` on the host. PostgreSQL does not expose a host port.

The production Dockerfile uses a non-root runtime user named `qaryati`.

## 8. Deployment Procedure

1. Install Docker Desktop or Docker Engine with Compose.
2. Prepare `.env.prod` using `.env.prod.example`.
3. Set strong, unique production secrets.
4. Review the configured CORS origins.
5. Start the services:

```bash
docker compose -f compose.prod.yml --env-file .env.prod up --build -d
```

6. Check service status:

```bash
docker compose -f compose.prod.yml --env-file .env.prod ps
```

7. Inspect API logs:

```bash
docker compose -f compose.prod.yml --env-file .env.prod logs api
```

8. Verify application endpoints and database connectivity.

## 9. Database Backups

Take regular PostgreSQL backups and store them securely outside the running containers.

Test restoration procedures before relying on backups for disaster recovery.

## 10. Rollback and Recovery

If a deployment fails:

1. Review application and migration logs.
2. Stop the affected deployment if necessary.
3. Restore the previously tested application image.
4. Assess database migration compatibility before attempting rollback.
5. Restore a verified database backup only when required.

Database migrations should not be reversed automatically without checking their effects on stored data.

## 11. Production Security Checklist

- [ ] Strong production credentials are configured.
- [ ] `.env.prod` is excluded from Git.
- [ ] JWT signing key is securely stored.
- [ ] CORS allows only trusted origins.
- [ ] Authentication rate limiting is enabled.
- [ ] Application logs do not expose secrets.
- [ ] Docker containers run as non-root users.
- [ ] PostgreSQL is not publicly exposed.
- [ ] Database migrations complete successfully.
- [ ] Database backups and restoration are tested.
- [ ] HTTPS is configured at the deployment entry point.
- [ ] Docker build and runtime checks pass.

## 12. Testing Status

The production Docker configuration has been reviewed, but Docker build and runtime verification are still pending because Docker is not currently available in the local development environment.