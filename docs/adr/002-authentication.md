# ADR-002: Authentication and authorization

## Status
Accepted

## Context
The API must be authenticated and authorized, with different permissions for
creating, editing, verifying and deleting village data.

## Decision
- Stateless JWT: short-lived access token (15 min) + longer refresh token (7 days),
  distinguished by a `type` claim so one cannot be used as the other.
- Passwords hashed with Argon2id (argon2-cffi). Never stored or logged in clear text.
- Four roles stored on the user: `admin`, `editor`, `verifier`, `viewer`.
  Public registration always yields `viewer`; only an admin can change roles.
- Authorization via a `require_roles(...)` dependency, so rules are declared at the route.
- The first admin is created with a CLI script, not through a public endpoint.
- Login returns the same error for unknown email and wrong password (no user enumeration).

## Consequences
+ No server-side session state; easy to scale horizontally.
+ Role checks are explicit and easy to test.
- Tokens cannot be revoked before they expire (a `jti` claim is included so a
  deny-list can be added later if needed).
- A role change takes effect for access tokens only after they expire or are refreshed
  (role is read from the DB on every request, so in practice it applies immediately).
