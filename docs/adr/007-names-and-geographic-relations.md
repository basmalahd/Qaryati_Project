# ADR-007: Alternative names and geographic relations

## Status
Accepted

## Context
Villages have several names (spellings, transliterations, former/historical names) and
geographic relationships to neighbouring villages and to cities that are not modelled.

## Decision
- **Names** live in `village_names` with a controlled `name_type`, optional language, period
  note and source. One row per (village, name, type) (UNIQUE) and a name may not repeat the
  village's *current* Arabic/English name. Alternative names are also searched by `GET /villages?q=`.
- **Relations** live in `nearby_places`: the target is *either* another village
  (`related_village_id`) *or* a free-text `place_name`, enforced by a CHECK constraint
  (exactly one), plus "not itself" and "distance >= 0" checks. Two partial unique indexes
  prevent duplicates for each kind of target (a plain UNIQUE would not, because NULLs are distinct).
- Relations are **directional and never mirrored automatically**: a hidden second write would
  complicate audit and consistency. If a symmetric link is wanted, both sides are added explicitly.
- Rows pointing to a deleted village are removed by `ON DELETE CASCADE` at database level.
- `elevation_m` (-500..3000) and `area_km2` (> 0) are optional columns with CHECK constraints,
  because the data is only modelled "when reliable data is available".
- All writes are audited (`village_name`, `nearby_place`), and every fact may cite a source.

## Consequences
+ Integrity is enforced by the database, not only by application code.
+ Provenance and audit work the same way as for population records.
- Symmetric relations need two explicit entries.
- Free-text places are not normalised (two spellings of one city are two places).
