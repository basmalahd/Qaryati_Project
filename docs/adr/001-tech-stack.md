# ADR-001: Backend technology stack and architecture style

## Status
Accepted

## Context
The specification requires a relational database with an ORM (plus selected native SQL cases),
versioned REST APIs, authentication and authorization, Docker, load testing and documentation. The
team has three developers, a short timeline and no user interface. The quality attributes we rank
highest are **testability, maintainability and security**, then **development efficiency**.
**Scalability** matters moderately: the data is read-heavy and can be scaled with more worker
processes or replicas.

## Decision
**Stack:** FastAPI with Pydantic, SQLAlchemy 2.0 (synchronous), Alembic, PostgreSQL 16, Docker
Compose, pytest and k6.

**Architecture:** a layered modular monolith, `API -> Services -> Repositories -> Models`. External
providers (geocoding) sit behind a port, so the port/adapter idea is applied only where the
specification asks for replaceability.

## Stack alternatives considered
| Option | Maintainability | Security | Testability | Scalability | Development efficiency | Verdict |
|---|---|---|---|---|---|---|
| **FastAPI + SQLAlchemy** | Typed schemas and explicit layers | Standard JWT and password libraries; validation at the edge | `Depends` lets tests replace the DB session and authentication | Stateless, scale by workers or replicas | OpenAPI generated from type hints, little boilerplate | **Chosen** |
| Spring Boot (Java) | Strong typing, mature ecosystem | Spring Security is very complete | Very good | Very good under heavy load | More boilerplate and a longer build/run cycle for a small team on a short timeline | Rejected: cost not justified by our load |
| NestJS / Express (Node) | Nest gives structure; plain Express leaves structure to us | Depends on the libraries we assemble | Good | Good | With Express we would assemble validation, ORM, OpenAPI and structure ourselves | Rejected: more decisions to assemble |
| Django REST Framework | Batteries included, strong conventions | Mature built-in auth | Good | Good | Fast to start | Rejected: the ORM and serializers pull business rules toward models and views, and OpenAPI needs an extra package |

PostgreSQL was chosen for integrity constraints (CHECK, unique, foreign keys) and window functions
used by the native SQL cases.

## Architecture alternatives considered
| Style | Advantages | Disadvantages for this project | Verdict |
|---|---|---|---|
| **Layered modular monolith** | One deployable unit; one database transaction covers a change and its audit entry (ADR-004); simple to test | Layer boundaries are kept by convention and review, not by tooling | **Chosen** |
| Full hexagonal / clean architecture | Domain fully independent of the ORM | Extra entity, ORM and DTO mapping for a mostly CRUD domain with modest business rules | Partly adopted (ports for external providers only) |
| Microservices | Independent deployment and scaling | Distributed transactions would break the atomic audit trail; operational overhead is not justified for one small bounded domain | Rejected |
| CQRS / event sourcing | Complete event history | High complexity; our `audit_logs` table and historical population records already give the needed history | Rejected |

## Consequences
+ Fast development, built-in OpenAPI documentation, typed request and response validation.
+ Business rules live in services, so most of them are tested without HTTP or a database.
- Synchronous SQLAlchemy keeps the code simple, but a worker is busy while it waits for the
  database. k6 showed requests queueing behind one worker; running 4 workers fixed it (ADR-012).
- Python is slower per request than the JVM (about 15 ms per request for one user in our
  measurements), which is acceptable for this workload.
- In-memory rate limiting is per process (ADR-010).
- Revisit when an asynchronous stack, a shared cache or several replicas become necessary.
