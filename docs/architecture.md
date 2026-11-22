# Architecture

**Style:** layered modular monolith (FastAPI). One deployable unit, clear layers, dependencies
point one way: `API -> Services -> Repositories -> Models`. External systems sit behind a *port*
(interface), so they can be replaced without touching business code. Rationale: ADR-001.

## 1. Components and dependency direction

```mermaid
flowchart TD
    client["Client: Swagger UI / API consumer"]

    subgraph api["API layer (FastAPI)"]
        mw["Request-ID middleware"]
        deps["Auth dependencies: JWT + role checks"]
        routers["Routers /api/v1/..."]
        errors["Global error handlers: unified error format"]
    end

    subgraph svc["Service layer: business rules + transactions"]
        authsvc["AuthService"]
        villagesvc["Village, name, nearby and content services (generic child service)"]
        popsvc["PopulationService: validation, conflicts, verification"]
        locsvc["LocationService"]
        auditsvc["AuditService"]
    end

    subgraph repo["Repository layer: data access"]
        orm["SQLAlchemy ORM repositories"]
        rawsql["Native SQL: stats query"]
    end

    subgraph integ["Integration layer: ports and adapters"]
        port["GeocodingProvider (port)"]
        cache["CachingGeocoder"]
        nominatim["NominatimGeocoder: timeout, retry, throttle"]
    end

    db[("PostgreSQL 16")]
    ext["Nominatim API (external)"]

    client --> mw --> routers
    routers --> deps
    routers --> authsvc
    routers --> villagesvc
    routers --> popsvc
    routers --> locsvc
    routers -.-> errors
    villagesvc --> auditsvc
    popsvc --> auditsvc
    authsvc --> orm
    villagesvc --> orm
    villagesvc --> rawsql
    popsvc --> orm
    auditsvc --> orm
    orm --> db
    rawsql --> db
    locsvc --> port
    port -.implemented by.-> cache
    cache --> nominatim
    nominatim --> ext

    classDef apiStyle fill:#dbeafe,stroke:#2563eb,color:#1e3a8a
    classDef svcStyle fill:#dcfce7,stroke:#16a34a,color:#14532d
    classDef repoStyle fill:#fef3c7,stroke:#d97706,color:#78350f
    classDef integStyle fill:#fae8ff,stroke:#a21caf,color:#581c87
    classDef extStyle fill:#e5e7eb,stroke:#4b5563,color:#111827
    class mw,deps,routers,errors apiStyle
    class authsvc,villagesvc,popsvc,locsvc,auditsvc svcStyle
    class orm,rawsql repoStyle
    class port,cache,nominatim integStyle
    class db,ext,client extStyle
```

| Layer | Responsibility | Must **not** |
|---|---|---|
| API (`app/api`) | HTTP, request/response validation, authentication, role checks | contain business rules or queries |
| Services (`app/services`) | Business rules, transaction boundary, audit, mapping external errors | know about HTTP or SQL details |
| Repositories (`app/repositories`) | Queries (ORM + one native SQL case), eager loading, pagination | decide business rules |
| Integrations (`app/integrations`) | Talk to external providers behind a port | leak provider details upward |
| Models / schemas | Tables (ORM) / request-response DTOs (Pydantic) | depend on upper layers |

## 2. Request flow: adding a population record

```mermaid
sequenceDiagram
    autonumber
    actor E as Editor
    participant R as Router
    participant D as Auth dependency
    participant S as PopulationService
    participant P as Repositories
    participant DB as PostgreSQL

    E->>R: POST /api/v1/villages/1/population with Bearer token
    R->>D: validate JWT, load user, check role
    D-->>R: current user (editor or admin)
    R->>S: create(village_id, data, actor)
    S->>P: village exists, source exists, no duplicate for this source and year
    P->>DB: SELECT
    S->>P: add population record and audit entry
    P->>DB: INSERT record and INSERT audit log (one transaction)
    S->>DB: COMMIT
    S-->>R: PopulationRead with has_conflict flag
    R-->>E: 201 Created
```

If any rule fails, the service raises a typed error (`NotFoundError`, `ConflictError`, ...) and
nothing is committed; the global handler turns it into the unified JSON error with a `traceId`.

## 3. Replaceable external provider (UML class diagram)

```mermaid
classDiagram
    class GeocodingProvider {
        <<interface>>
        +search(query, limit, country_code) list~GeoLocation~
    }
    class NominatimGeocoder {
        -max_retries
        -min_interval
        +search(query, limit, country_code) list~GeoLocation~
    }
    class CachingGeocoder {
        -ttl
        -empty_ttl
        +search(query, limit, country_code) list~GeoLocation~
    }
    class TTLCache {
        +get(key)
        +set(key, value, ttl_seconds)
    }
    class LocationService {
        +suggest_for_village(village_id)
        +search(q, limit)
    }

    GeocodingProvider <|.. NominatimGeocoder
    GeocodingProvider <|.. CachingGeocoder
    CachingGeocoder o-- GeocodingProvider : wraps
    CachingGeocoder *-- TTLCache
    LocationService --> GeocodingProvider : depends on the port only
```

Switching provider = one new class implementing `GeocodingProvider` and one line in `build_geocoder`
(see ADR-006).

## 4. Roles

```mermaid
flowchart LR
    viewer["viewer"] -->|read| data["Villages, population, names, sources"]
    editor["editor"] -->|create and edit| data
    editor -->|geocoding suggestions| geo["Geocoding"]
    verifier["verifier"] -->|verify or dispute population| pop["Population status"]
    admin["admin"] -->|all of the above, delete, roles| data
    admin --> audit["Audit log"]
    admin --> users["User roles"]
```
