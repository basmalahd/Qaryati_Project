# Database schema (ERD)

PostgreSQL 16, managed with Alembic migrations (`alembic/versions/0001` ... `0006`).
Every fact that can be disputed (population, names, relations) can point to a row in `sources`.

```mermaid
erDiagram
    governorates ||--o{ villages : "contains"
    villages ||--o{ village_names : "has alternative names"
    villages ||--o{ population_records : "has population history"
    villages ||--o{ nearby_places : "has relations (from)"
    villages |o--o{ nearby_places : "is the target of (to)"
    sources ||--o{ population_records : "is the source of"
    sources |o--o{ village_names : "may be the source of"
    sources |o--o{ nearby_places : "may be the source of"
    users |o--o{ audit_logs : "performs"
    villages ||--o{ historical_events : "has timeline"
    villages ||--o{ landmarks : "has landmarks"
    villages ||--o{ heritage_items : "has heritage"
    villages ||--o{ economic_items : "has economy"
    villages ||--o{ facilities : "has facilities"
    sources |o--o{ historical_events : "may be the source of"
    sources |o--o{ landmarks : "may be the source of"
    sources |o--o{ heritage_items : "may be the source of"
    sources |o--o{ economic_items : "may be the source of"
    sources |o--o{ facilities : "may be the source of"

    governorates {
        int id PK
        varchar name_ar UK
        varchar name_en UK
    }

    villages {
        int id PK
        varchar slug UK
        varchar name_ar
        varchar name_en
        text name_origin
        text historical_overview
        float latitude
        float longitude
        float elevation_m
        float area_km2
        int governorate_id FK
        timestamptz created_at
        timestamptz updated_at
    }

    village_names {
        int id PK
        int village_id FK
        varchar name
        varchar language
        varchar name_type
        varchar period_note
        int source_id FK
        timestamptz created_at
        timestamptz updated_at
    }

    population_records {
        int id PK
        int village_id FK
        int population
        int reference_year
        int source_id FK
        varchar verification_status
        text notes
        timestamptz created_at
        timestamptz updated_at
    }

    nearby_places {
        int id PK
        int village_id FK
        int related_village_id FK
        varchar place_name
        varchar relation_type
        float distance_km
        varchar direction
        int source_id FK
        timestamptz created_at
        timestamptz updated_at
    }

    sources {
        int id PK
        varchar title
        varchar source_type
        varchar author
        varchar url
        int publication_year
        text notes
        timestamptz created_at
        timestamptz updated_at
    }

    users {
        int id PK
        varchar email UK
        varchar full_name
        varchar hashed_password
        varchar role
        boolean is_active
        timestamptz created_at
        timestamptz updated_at
    }

    audit_logs {
        int id PK
        int user_id FK
        varchar action
        varchar entity_type
        int entity_id
        json changes
        timestamptz created_at
    }

    historical_events {
        int id PK
        int village_id FK
        varchar title
        text description
        int year
        varchar date_note
        int source_id FK
        timestamptz created_at
        timestamptz updated_at
    }

    landmarks {
        int id PK
        int village_id FK
        varchar name_ar
        varchar name_en
        varchar category
        text description
        float latitude
        float longitude
        int source_id FK
        timestamptz created_at
        timestamptz updated_at
    }

    heritage_items {
        int id PK
        int village_id FK
        varchar name
        varchar category
        text description
        int source_id FK
        timestamptz created_at
        timestamptz updated_at
    }

    economic_items {
        int id PK
        int village_id FK
        varchar name
        varchar category
        text description
        int source_id FK
        timestamptz created_at
        timestamptz updated_at
    }

    facilities {
        int id PK
        int village_id FK
        varchar name
        varchar facility_type
        text description
        int source_id FK
        timestamptz created_at
        timestamptz updated_at
    }
```

`audit_logs.entity_type` + `entity_id` is a deliberate *generic* reference (no foreign key):
one table audits every entity, and the history survives when the audited row is deleted.

## Important modeling decisions

| Decision | Why |
|---|---|
| Population is a **history table**, not a column on `villages` | A village has many values over time from different references |
| `population_records.source_id` is `NOT NULL` with `ON DELETE RESTRICT` | Provenance is mandatory and a cited source can never disappear |
| `UNIQUE (village_id, reference_year, source_id)` | One value per source and year; *different* sources may disagree and both are kept (conflicts are flagged, never overwritten) |
| `verification_status` (`pending` / `verified` / `disputed`) | Review state is part of the data, so unreviewed numbers are never presented as verified |
| `village_names` is separate from `villages` | Many alternative / historical names per village, each with type, period and source |
| `UNIQUE (village_id, name, name_type)` on `village_names` | No duplicate names |
| `nearby_places` target is **either** a village **or** free text | `CHECK` enforces exactly one, so a city that is not modelled can still be recorded |
| Two *partial* unique indexes on `nearby_places` | A plain `UNIQUE` would not work because `NULL` values are distinct |
| Relations are directional, no automatic mirror | Avoids hidden writes that would complicate audit and consistency |
| `CHECK` constraints (population >= 0, year range, area > 0, elevation range, enums) | Integrity is enforced by the database, not only by application code |
| `ON DELETE CASCADE` for dependent rows (names, population, relations) | Deleting a village leaves no orphans; `audit_logs.user_id` uses `SET NULL` to keep history |
| Indexes on `villages(name_ar, name_en, governorate_id)`, `population_records(village_id, reference_year)`, `audit_logs(entity_type, entity_id)` | Support search, population history and audit lookups |
| Timeline entries need a year **and/or** a free-text period (`CHECK`) | Historical facts are often only known approximately ("late Ottoman period") |
| Content tables (events, landmarks, heritage, economy, facilities) share one shape: `village_id` (CASCADE) + optional `source_id` (SET NULL) | Same provenance and cleanup rules everywhere; implemented once in `VillageChildService` (ADR-008) |
| Categories / types are `CHECK`-constrained enums, `UNIQUE (village_id, name, category)` | Controlled vocabulary, no duplicates, same name allowed in different categories |
| Facilities are plain descriptive rows | Supporting context only: the platform is not a municipal service-management system |
