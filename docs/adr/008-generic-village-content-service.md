# ADR-008: One generic service for village-owned content

## Status
Accepted

## Context
Events, landmarks, heritage items, economic items and facilities all follow the same rules:
the village must exist, a cited source must exist, duplicates are rejected, every write is audited
in the same transaction, and reads are eager-loaded. Writing five copies would violate the
"avoid repeated logic" requirement and multiply the places a rule can be forgotten.

## Decision
- `VillageChildRepository` (data access) and `VillageChildService` (rules + transaction + audit)
  implement the shared behaviour once. A subclass declares only what is specific: model,
  `unique_keys`, `ordering()`, an optional `validate_state()` and its filtered `list()`.
- `VillageChildMixin` gives the tables the same columns (`village_id` CASCADE, `source_id` SET NULL).
- Routers share one `_mount_write_routes()` for POST/PATCH/DELETE; each resource keeps its own GET
  because its filters differ (category, type, year range).
- Resources with genuinely different rules keep their own services (population records have a
  verification workflow, nearby places have a target rule).

## Consequences
+ A new content type = one model + schemas + a ~10-line service subclass; rules and audit come for free.
+ One set of behaviour to test; a parametrized test suite covers all five resources.
- A small amount of indirection (hooks) to understand; deliberate trade-off against duplication.
- If a resource's rules diverge a lot, it should leave the generic base rather than bend it.
