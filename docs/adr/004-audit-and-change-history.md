# ADR-004: Audit trail and handling of changes

## Status
Accepted

## Context
Historical and demographic data is sensitive: the project requires that important
changes are auditable (who, when) and that data is never silently overwritten.

## Decision
- A single `audit_logs` table stores `user_id`, `action` (create/update/delete),
  `entity_type`, `entity_id`, a JSON `changes` payload (`before`/`after` of the
  fields that really changed) and a server-side timestamp.
- The audit row is written in the **same transaction** as the change (service layer
  commits once), so a change can never exist without its audit entry or vice versa.
- A PATCH that changes nothing writes nothing (no audit noise).
- Deletes are hard deletes; the full previous state is kept in the audit entry.
- The audit trail is readable only by admins (`GET /api/v1/audit-logs`).

## Consequences
+ Full accountability with one generic mechanism reusable for every entity.
+ Atomicity guaranteed by the transaction boundary.
- Hard delete loses referential history in the live tables (kept only in the audit log);
  soft delete could be added later if "restore" becomes a requirement.
- `user_id` becomes NULL if a user is ever deleted (history is kept).
