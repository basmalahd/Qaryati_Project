# ADR-012: Run the API with several worker processes

## Status
Accepted

## Context
k6 measurements (see `docs/performance.md`) showed that a request needs about 15 ms to be
processed with one concurrent user but 113 ms on average with 20 users. PostgreSQL executes the
search in about 1 to 2 ms, so the delay was not in the database. The API ran as a single
uvicorn process with `--reload` (the development command in the `Dockerfile`), so concurrent
requests waited for each other.

## Decision
- Run uvicorn **without `--reload` and with 4 workers** when benchmarking and in any
  production-like run. The override lives in `performance/docker-compose.perf.yml`
  (`docker compose -f docker-compose.yml -f performance/docker-compose.perf.yml up -d --force-recreate api`).
- The development `Dockerfile` command is unchanged here; the production container setup is
  handled in the Docker/production task.

## Alternatives considered
- **`pg_trgm` GIN index on village names.** Rejected: `EXPLAIN ANALYZE` showed the search takes
  1.2 ms and the count 1.9 ms, so an index cannot remove the observed latency.
- **Caching read responses.** Not needed to remove this bottleneck; would add invalidation
  complexity (audit log, verification status) for no measured gain.

## Consequences
+ With 4 workers: read avg 113 -> 47 ms (-59 %), p95 207 -> 133 ms, throughput +40 %; write avg
  90 -> 37 ms (-59 %), p95 194 -> 78 ms, throughput +27 %. Error rate stayed at 0 %.
+ 8 workers were also tested: reads about the same as 4 (avg 44 ms), writes slower than 4
  (avg 55 ms). 4 is kept; the difference may be noise because each figure is a single run.
- **Rate limiting is per process** (`app/core/rate_limit.py` keeps counters in memory), so with
  4 workers the effective limit is up to 4 times the configured value. A shared store (for
  example Redis) is required for exact limits.
- **The geocoding cache and throttle are per process** (`get_geocoder` is cached per process),
  so each worker has its own cache and external-provider throttle.
- Database connections multiply: each worker has its own SQLAlchemy pool (default 5 plus 10
  overflow), so up to 60 connections with 4 workers; this must stay below PostgreSQL's
  `max_connections` (default 100).
- Without `--reload`, code changes need a container restart.
- Latency under load (47 ms) is still above single-user latency (16 ms); we did not find out why.
