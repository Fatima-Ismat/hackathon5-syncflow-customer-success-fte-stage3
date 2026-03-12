# Load Test Summary
## SyncFlow Customer Success Digital FTE — Stage 3

**Owner:** Ismat Fatima | **Hackathon 5 — Stage 3 Final**

> **Instructions:** Fill in the actual results after running the load test.
> Replace all `[FILL IN]` placeholders with real values.

---

## Test Configuration

| Parameter | Value |
|-----------|-------|
| Tool | Locust 2.x |
| Test file | `tests/load_test.py` |
| Target host | `http://localhost:8000` (local) / `[FILL IN HF URL]` (production) |
| Users | 50 |
| Spawn rate | 5 users/second |
| Duration | 60 seconds |
| User classes | `SupportFormUser`, `TicketLookupUser`, `WebhookSimulator` |

---

## Run Commands

### Local Load Test

```bash
# Prerequisites: API must be running
uvicorn api.main:app --port 8000 &

# Install Locust (if not installed)
pip install locust

# Run headless — 50 users, 60 seconds
locust -f tests/load_test.py \
  --host=http://localhost:8000 \
  --users=50 \
  --spawn-rate=5 \
  --run-time=60s \
  --headless \
  --html=reports/load-report-local.html \
  --csv=reports/load-local

# View HTML report
open reports/load-report-local.html   # macOS
start reports/load-report-local.html  # Windows
```

### Production Load Test (HF Space)

```bash
locust -f tests/load_test.py \
  --host=https://ismat110-syncflow-api.hf.space \
  --users=20 \
  --spawn-rate=2 \
  --run-time=60s \
  --headless \
  --html=reports/load-report-prod.html \
  --csv=reports/load-prod
```

### Interactive UI (for recording)

```bash
locust -f tests/load_test.py --host=http://localhost:8000
# Open: http://localhost:8089
# Set users=50, spawn-rate=5, then Start
```

---

## User Behavior Classes

| Class | Tasks | Weight Distribution |
|-------|-------|-------------------|
| `SupportFormUser` | Normal web form submission, angry message (escalation trigger), health check, channel check | 6:2:1:3 |
| `TicketLookupUser` | List tickets, get metrics summary, get channel breakdown, customer profile, ticket by ref (404 test), sentiment metrics | 4:2:2:1:3:1 |
| `WebhookSimulator` | Gmail webhook events, WhatsApp webhook events | 3:2 |

---

## Results (Fill In After Running)

### Response Time Percentiles

| Endpoint Group | p50 (ms) | p95 (ms) | p99 (ms) | Target |
|---------------|----------|----------|----------|--------|
| `POST /support/submit` | [FILL IN] | [FILL IN] | [FILL IN] | p95 < 2000ms |
| `GET /tickets` | [FILL IN] | [FILL IN] | [FILL IN] | p95 < 500ms |
| `GET /metrics/summary` | [FILL IN] | [FILL IN] | [FILL IN] | p95 < 500ms |
| `POST /webhooks/gmail` | [FILL IN] | [FILL IN] | [FILL IN] | p95 < 200ms |
| `POST /webhooks/whatsapp` | [FILL IN] | [FILL IN] | [FILL IN] | p95 < 200ms |
| `GET /health` | [FILL IN] | [FILL IN] | [FILL IN] | p95 < 50ms |
| **Overall** | [FILL IN] | [FILL IN] | [FILL IN] | p95 < 2000ms |

### Throughput and Reliability

| Metric | Result | Target |
|--------|--------|--------|
| Total requests | [FILL IN] | — |
| Requests/second (peak) | [FILL IN] | > 10 req/s at 10 users |
| Requests/second (at 50 users) | [FILL IN] | — |
| Total failures | [FILL IN] | < 1% of requests |
| Failure rate | [FILL IN] % | < 1% |
| Max concurrent users sustained | [FILL IN] | 50 |

### Error Breakdown (if any)

| Error | Count | % | Root Cause |
|-------|-------|---|------------|
| [FILL IN or "None"] | — | — | — |

---

## Performance Targets vs Actuals

| Target | Required | Actual | Pass? |
|--------|----------|--------|-------|
| p50 response time | < 500ms | [FILL IN] | [✅/❌] |
| p95 response time | < 2000ms | [FILL IN] | [✅/❌] |
| p99 response time | < 5000ms | [FILL IN] | [✅/❌] |
| Error rate | < 1% | [FILL IN] | [✅/❌] |
| Throughput (10 users) | > 10 req/s | [FILL IN] | [✅/❌] |
| Health check latency | < 50ms | [FILL IN] | [✅/❌] |

---

## Screenshot Placeholder

```
📸 [INSERT LOCUST HTML REPORT SCREENSHOT HERE]
   File: docs/screenshots/14-load-test-report.png

   Should show:
   - Response time chart over the test duration
   - Requests/second chart
   - User count ramp-up
   - Final statistics table (p50/p95/p99/failures per endpoint)
```

---

## Observations and Notes

> **[FILL IN]** — Add any observations about:
> - Which endpoint was the bottleneck (if any)
> - Whether SQLite showed locking under load (expected with WORKERS=1)
> - Memory usage during test
> - Any spikes or anomalies

---

## Known Constraints

| Constraint | Impact on Load Test |
|------------|-------------------|
| `WORKERS=1` (SQLite single-writer) | Sequential writes limit throughput; normal for demo |
| HF free tier cold start | First request to sleeping Space takes ~30s; excluded from metrics |
| In-memory mock Kafka | Zero network overhead; production Kafka would add latency |
| No connection pooling for SQLite | `aiosqlite` handles concurrency but with contention under high write load |

For a production load test with PostgreSQL + real Kafka:
```bash
export DATABASE_URL="postgresql://..."
export KAFKA_MOCK_MODE=false
export WORKERS=4
uvicorn api.main:app --workers 4 --port 8000
```
