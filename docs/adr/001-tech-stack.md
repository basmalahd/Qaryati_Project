# ADR-001: Backend technology stack

## Status
Accepted

## Context
We need a backend with ORM + raw SQL support, strong validation,
automatic API docs, and fast development within a short timeline.

## Decision
FastAPI, SQLAlchemy 2.0, Alembic, PostgreSQL 16, Docker.

## Consequences
+ Fast development, built-in OpenAPI docs, good testability.
+ Pydantic gives typed request/response validation.
- Python is slower than JVM under heavy load (mitigated by caching/indexing).
- Sync SQLAlchemy chosen for simplicity.
