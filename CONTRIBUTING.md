# Contributing

The team: **Basmala**, **Shaymaa**, **Hanaa**. Everyone works through branches and Pull Requests
under her own GitHub account; nobody pushes to `main` directly.

## Workflow
1. Pick (or create) an Issue and assign it to yourself.
2. Update and branch off `main`:
   ```
   git checkout main && git pull
   git checkout -b feature/short-name
   ```
   Prefixes: `feature/`, `fix/`, `docs/`, `chore/`, `perf/`, `test/`.
3. Make small, focused commits with meaningful messages:
   `feat: add rate limiting to login`, `fix: ...`, `docs: ...`, `test: ...`, `chore: ...`, `perf: ...`, `refactor: ...`.
4. Run the tests (`pytest`) before pushing. Push and open a Pull Request using the template.
5. Another member reviews (rotation: Basmala -> Shaymaa -> Hanaa -> Basmala). Address comments, then merge.
6. The branch is deleted automatically after merging. Pull `main` before starting the next task.

## Rules
- One purpose per PR; keep PRs small enough to review in a few minutes.
- Never commit secrets, `.env`, build output or generated files.
- Schema changes need an Alembic migration, and `alembic check` must be clean.
- New behaviour needs tests (unit and/or integration, see `docs/testing-strategy.md`); important decisions need a short ADR in `docs/adr/`.
- ADR numbers are reserved to avoid clashes: 009 testing (Basmala), 010 rate limiting and 011 logging (Shaymaa), 012 indexing and caching (Hanaa). Later ones take the next free number.
- Files that cause merge conflicts easily (`app/main.py`, `app/core/config.py`,
  `app/api/v1/router.py`, `requirements.txt`, `README.md`): pull often and keep changes there small.

## Code structure (where things go)
`API (routers, deps) -> services (rules, transactions, audit) -> repositories (queries) -> models`.
External systems sit behind a port in `app/integrations/`. See `docs/architecture.md`.

## Areas of responsibility
| Member | Area |
|---|---|
| Basmala | Test structure, API documentation, engineering-decisions register, final README, review/integration |
| Shaymaa | Configuration per environment, CORS, rate limiting, structured logging, CI, Docker production setup, security docs |
| Hanaa | Seed data, k6 load tests, performance analysis and optimization, performance report |
