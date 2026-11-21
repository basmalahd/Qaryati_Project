# ADR-005: Population records - validation, provenance and conflicts

## Status
Accepted

## Context
Population is historical and comes from different references that may disagree.
The project requires source/reference metadata, explicit validation and consistency
rules, and a strategy for conflicting data instead of silent overwriting.

## Decision
Rules enforced in `PopulationService` (and mirrored by DB constraints where possible):
1. A record always has a `source_id` (NOT NULL, FK with RESTRICT: sources cannot be deleted while used).
2. `population >= 0`, `1800 <= reference_year <= current year` (DB: 1800..2100).
3. One record per (village, year, source) - UNIQUE constraint + friendly 409.
4. **Conflicts are kept, not resolved automatically**: different sources may report
   different values for the same year; both stay, and reads expose `has_conflict`.
5. Verification workflow: `pending -> verified | disputed`. Only `verifier`/`admin`
   change status; only `editor`/`admin` change values (separation of duties).
6. **Verified records are locked.** To correct one, a verifier first marks it `disputed`.
   Any edit returns the record to `pending` so changed data is never shown as verified.
7. Every create/update/status change/delete is written to the audit log in the same transaction.

## Consequences
+ Provenance and review state are part of the data model, not an afterthought.
+ No silent overwrite; history of who changed what is preserved.
- Consumers must handle several records per year (they decide which source to trust).
- A verifier can verify any record, including one they created in another role
  (a "four-eyes" check would need a `created_by` column - possible future work).
