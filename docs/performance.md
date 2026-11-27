# Performance report

## 1. Goal and method

Find the main bottleneck of the read and write paths with measurements, apply **one**
improvement, and measure again under identical conditions.

| Item | Value |
|---|---|
| Tool | k6 2.4.0 (`performance/k6/read.js`, `performance/k6/write.js`) |
| Data | 2000 seeded villages, 16 200 population records (`app.scripts.seed_performance_data`) |
| Read load | ramp to 20 virtual users (VUs), 75 s; search, list by governorate, village detail, population history |
| Write load | ramp to 10 VUs, 75 s; create village, update (PATCH), add population record |
| Environment | Docker Desktop on Windows (16 CPUs available), API + PostgreSQL 16 in containers, k6 on the same machine |
| Rate limiting | **Disabled during measurement** (`RATE_LIMIT_ENABLED=false`), see 2.1 |
| Metrics | `http_req_duration` (avg, p95), `http_reqs` (throughput), `http_req_failed` (error rate) |

Raw k6 summaries are in `performance/results/`.

## 2. Findings

### 2.1 First run was invalid: the rate limiter was measured, not the API

With rate limiting enabled, 97.9 % of requests failed (search and list succeeded only about 2 %
of the time) and the average latency looked like 5 ms because rejected requests are cheap.
Those numbers were discarded. The limiter was disabled for the benchmark. Its own behaviour
(HTTP 429) is covered by ADR-010 and its tests.

### 2.2 Baseline (1 uvicorn worker, `--reload`)

| Metric | Read (20 VUs) | Write (10 VUs) |
|---|---|---|
| avg latency | 113.4 ms | 90.3 ms |
| p95 latency | 207.5 ms | 194.3 ms |
| Throughput | 80.4 req/s | 38.1 req/s |
| Error rate | 0 % | 0 % |

All four read endpoints had almost the same latency (109 to 119 ms on average), even a
single-row lookup by id. That pointed away from any one query.

### 2.3 Hypothesis 1 (rejected): the search needs an index

The search uses `ILIKE '%text%'`, which a B-tree index cannot serve, so a trigram (`pg_trgm`)
index looked like the obvious fix. `EXPLAIN (ANALYZE, BUFFERS)` on PostgreSQL showed:

| Query | Execution time |
|---|---|
| Search (`ILIKE` on name_ar / name_en, `LIMIT 20`) | 1.2 ms |
| `COUNT(*)` used for pagination (sequential scan of 2000 rows) | 1.9 ms |

The database accounts for roughly 2 % of the 113 ms request time, so an index would not
measurably change the result. No index was added.

### 2.4 Hypothesis 2 (supported): requests queue behind a single worker

Same code, same data, same queries, different number of concurrent users:

| Users | avg | p95 |
|---|---|---|
| 1 VU | 16.4 ms | 24.2 ms |
| 20 VUs | 113.4 ms | 207.5 ms |

Processing one request takes about 15 ms; the remaining ~100 ms under load is waiting time.
The API ran as one process (`uvicorn ... --reload`), so concurrent requests were served
one behind another and throughput flattened at about 80 req/s.
We did not directly record CPU usage of the container during the load, so this is the
explanation best supported by the latency data, not a profiler result.

## 3. Improvement applied

Run the API **without `--reload` and with 4 worker processes** (`performance/docker-compose.perf.yml`).
Only the start command differs; image, environment and data are the same. Decision and
trade-offs: ADR-012. The number of workers was confirmed for every run with
`docker compose top api` (4 or 8 `spawn_main` processes). To see whether more workers help, the
same tests were also run with 8 workers.

## 4. Results

Read test, 20 VUs:

| Metric | 1 worker (before) | 4 workers | 8 workers |
|---|---|---|---|
| avg latency | 113.4 ms | 46.9 ms (-59 %) | 44.0 ms (-61 %) |
| p95 latency | 207.5 ms | 133.3 ms (-36 %) | 116.5 ms (-44 %) |
| Throughput | 80.4 req/s | 112.6 req/s (+40 %) | 113.9 req/s (+42 %) |
| Error rate | 0 % | 0 % | 0 % |

Write test, 10 VUs:

| Metric | 1 worker (before) | 4 workers | 8 workers |
|---|---|---|---|
| avg latency | 90.3 ms | 37.1 ms (-59 %) | 54.8 ms (-39 %) |
| p95 latency | 194.3 ms | 78.0 ms (-60 %) | 142.3 ms (-27 %) |
| Throughput | 38.1 req/s | 48.3 req/s (+27 %) | 43.8 req/s (+15 %) |
| Error rate | 0 % | 0 % | 0 % |

Reading the tables:
- Going from 1 to 4 workers gives most of the gain on both read and write.
- 8 workers add little for reads (avg 47 to 44 ms, throughput unchanged) and were slower than 4
  workers for writes. We therefore keep **4 workers**.
- Each figure is one 75 s run, so we cannot tell whether the difference between 4 and 8 workers
  is real or measurement noise, and we did not investigate why 8 workers were not better.
- The write load is limited partly by the test itself (10 VUs with think time).

## 5. Limitations

- Single runs on a developer laptop; k6 and Docker share the same machine, so absolute numbers
  will differ elsewhere. Compare ratios, not absolutes.
- With 4 and 8 workers latency (44 to 47 ms) is still above the single-user latency (16 ms).
  `docker compose top` showed CPU time spread very unevenly across workers (with 8 workers, one
  process used about 1 minute of CPU and the others 4 to 11 seconds). We did not measure why.
- The dataset is small (2000 villages). Search behaviour on a much larger table was not measured;
  the `EXPLAIN` result above applies to this size only.

## 6. Next steps (not done)

- Measure with CPU and per-worker metrics during load to find what limits the 4-worker setup.
- Re-run `EXPLAIN` on a larger dataset; add a `pg_trgm` GIN index only if the search becomes
  the dominant cost.
- Replace the in-memory rate limiter with a shared store (for example Redis) before relying on it
  with several workers.
