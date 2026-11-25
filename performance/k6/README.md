# k6 performance scripts

| Script | What it tests |
|---|---|
| `read.js`  | village search, listing by governorate, village details, population history |
| `write.js` | create village, update village (PATCH), add population record |

## 1. Prepare (once)

```bash
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api python -m app.scripts.seed_performance_data --villages 2000
docker compose exec api python -m app.scripts.create_admin --email k6-admin@example.com --name "k6 admin" --password ChangeMe12345
```

## 2. Install k6
https://grafana.com/docs/k6/latest/set-up/install-k6/  (Windows: `winget install k6`)

## 3. Run
```bash
k6 run performance/k6/read.js
k6 run performance/k6/write.js
# save a machine-readable summary for the report:
k6 run --summary-export=performance/results/read-before.json performance/k6/read.js
```
Options: `-e VUS=50 -e DURATION=2m -e BASE_URL=http://localhost:8000`

## 4. Clean up write-test data
```bash
docker compose exec api python -m app.scripts.seed_performance_data --clean
# k6-created rows (slug seed-village-k6-*) are removed by this too only if the script's LIKE matches:
# 'seed-village-%' -> yes, they are covered.
```

## Metrics to put in docs/performance.md
`http_req_duration` avg and p(95), `http_reqs` (throughput = requests/s),
`http_req_failed` (error rate). Run **before** the optimisation and **after**, same VUS/DURATION.

> If rate limiting (ADR-010) is enabled, k6 will get 429s. Raise the limit or disable it in the
> test environment, otherwise you measure the limiter, not the API.
