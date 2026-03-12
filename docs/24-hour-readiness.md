# 24-Hour Readiness Plan
## SyncFlow Customer Success Digital FTE — Stage 3

**Owner:** Ismat Fatima | **Hackathon 5 — Stage 3 Final**

---

## Overview

This document describes how SyncFlow handles a 24-hour continuous operation scenario: restarts, external service failures, webhook delivery retries, overload conditions, and chaos events.

---

## 1. System Restart Resilience

### What happens on container restart

| Step | Behavior |
|------|---------|
| Container starts | `startup.sh` runs |
| Seed script | `python database/seed.py` — non-fatal; `|| echo` skips on error without blocking |
| Database connection | SQLAlchemy `create_all()` creates tables if they don't exist; idempotent |
| API start | `exec uvicorn` receives `SIGTERM` cleanly; in-flight requests complete before shutdown |
| Kafka mock | `MockKafkaBroker` reinitializes in memory; zero external dependencies |
| Health probe | `GET /health` becomes healthy as soon as uvicorn is accepting connections |

### Kubernetes restart behavior

```yaml
# k8s/deployment-api.yaml
livenessProbe:
  httpGet:
    path: /health
    port: 8000
  initialDelaySeconds: 15
  periodSeconds: 30
  failureThreshold: 3

readinessProbe:
  httpGet:
    path: /readiness
    port: 8000
  initialDelaySeconds: 10
  periodSeconds: 10
```

- Failed pod → K8s restarts automatically within ~30s
- Readiness probe prevents traffic routing until API is warm
- HPA replaces unhealthy replicas transparently

### HF Spaces restart behavior

- Space sleeps after 48h inactivity (free tier)
- `startup.sh` handles cold start: seed → start API
- First request wakes the Space (30s delay is normal)
- Health endpoint returns 200 as soon as the container is warm

---

## 2. Webhook Retry Behavior

### Gmail webhook (Google Pub/Sub push)

| Scenario | Behavior |
|---------|---------|
| API returns HTTP 200 | Pub/Sub considers message delivered; no retry |
| API returns non-200 or timeout | Pub/Sub retries with exponential backoff: 10s → 20s → 40s → up to 10min |
| API is down for > 7 days | Pub/Sub drops message (dead-letter topic recommended in production) |
| Webhook processed but OpenAI times out | Ticket still created with rule-based AI response; escalation proceeds normally |

Our webhook handler returns 200 immediately and processes in `BackgroundTasks`:
```python
# api/main.py
@app.post("/webhooks/gmail")
async def gmail_webhook(payload: dict, background_tasks: BackgroundTasks):
    background_tasks.add_task(_process_message, ...)
    return {"accepted": True}   # ← returned before processing starts
```

### WhatsApp webhook (Twilio)

| Scenario | Behavior |
|---------|---------|
| API returns HTTP 200 | Twilio marks message delivered |
| API returns non-200 | Twilio retries up to 3 times over 5 minutes |
| Invalid Twilio signature | `400 Bad Request` returned; Twilio logs error and retries |
| Twilio sandbox (dev) | No signature validation; `TWILIO_AUTH_TOKEN` not required |

### Duplicate webhook protection

Currently: no deduplication (demo scope). In production, add:
```python
# Check message_id in Redis or DB before processing
if await db_message_exists(message_id):
    return {"accepted": True, "duplicate": True}
```

---

## 3. Kafka Fallback Behavior

### Fallback hierarchy

```
Real Kafka (Confluent Cloud)
  │  KAFKA_MOCK_MODE=false + KAFKA_BOOTSTRAP_SERVERS set
  │
  ▼ if connection fails at startup
In-Memory Mock Broker (MockKafkaBroker)
  │  KAFKA_MOCK_MODE=true (default)
  │  thread-safe deque, unlimited capacity
  │
  ▼ if publish() raises exception
Silent skip + log warning
  │  Processing continues; ticket still created
  │  Kafka failure is non-fatal
```

### Kafka failure scenario

If real Kafka becomes unavailable mid-operation:
1. `kafka_client.py` publish calls raise `KafkaException`
2. `api/main.py` wraps publish in `try/except` — exception is logged, not raised
3. Ticket creation, AI response, and escalation all complete normally
4. Kafka events are lost for that window (no replay in mock mode)
5. System auto-reconnects on next publish attempt

### Dead-letter queue

Topic `fte.dead-letter` receives events that fail consumer processing:
```python
# workers/message_processor.py
try:
    process_event(event)
except Exception as e:
    kafka_client.publish("fte.dead-letter", {"original": event, "error": str(e)})
```

Events in `fte.dead-letter` can be replayed manually:
```bash
# Replay dead-letter events (production)
kafka-consumer-groups --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS \
  --reset-offsets --to-earliest --topic fte.dead-letter --execute
```

---

## 4. Database Outage Fallback

### Fallback hierarchy

```
PostgreSQL (production)
  DATABASE_URL=postgresql://...
  │
  ▼ if connection fails at startup
SQLite (development / fallback)
  DATABASE_URL=sqlite:///./syncflow_dev.db
  │
  ▼ if DATABASE_URL=sqlite:// (in-memory)
In-memory SQLite (tests / emergency)
  Zero persistence; resets on restart
```

### Automatic fallback

`database/connection.py` does not auto-detect PostgreSQL failure at runtime. If PostgreSQL becomes unavailable after startup:
- Active connections fail with `sqlalchemy.exc.OperationalError`
- API returns `500 Internal Server Error` for database-dependent endpoints
- `/health` endpoint reflects `{"database": "degraded"}`
- `/readiness` returns HTTP 503 (pod removed from load balancer)

### Emergency fallback procedure

```bash
# Switch to SQLite without restarting the entire K8s cluster
kubectl set env deployment/syncflow-api \
  DATABASE_URL=sqlite:///./syncflow_emergency.db \
  -n syncflow

# Or for HF Spaces — update secret:
# DATABASE_URL = sqlite:///./syncflow_emergency.db
# (Space will restart automatically)
```

### Data durability

| Mode | Durability |
|------|-----------|
| PostgreSQL | Full ACID; 8 tables with foreign keys and indexes |
| SQLite file | Single-writer; data survives restarts but not container recreation |
| SQLite in-memory | Test only; no persistence |
| HF Spaces (SQLite) | File survives Space restarts but NOT Space rebuilds |

**Recommendation for 24h production:** Use PostgreSQL (Neon free tier) with `DATABASE_URL` set as HF secret.

---

## 5. Chaos Testing Plan

### Simulated tests (run locally)

```bash
# Test 1: Burst load across all channels
pytest -m slow -v
# Test: Test24HourReadiness — 10 concurrent requests, ≥8/10 must succeed

# Test 2: Locust 50-user profile for 60 seconds
locust -f tests/load_test.py --host=http://localhost:8000 \
  --users=50 --spawn-rate=5 --run-time=60s --headless

# Test 3: Kill API mid-request (restart test)
# Run: uvicorn api.main:app --port 8000 &
# Submit a request, then: kill -SIGTERM $(lsof -ti:8000)
# Verify: API restarts cleanly, no corrupt DB state
```

### Manual chaos scenarios

| Scenario | How to Trigger | Expected Behavior |
|---------|---------------|------------------|
| Kafka down | `KAFKA_MOCK_MODE=false` + wrong broker | Falls back to silent skip; tickets still created |
| OpenAI key invalid | Set `OPENAI_API_KEY=invalid` | Rule-based fallback activates; all requests succeed |
| PostgreSQL unreachable | Wrong `DATABASE_URL` | API returns 500; `/health` shows degraded |
| High sentiment burst | Send 10 angry messages at once | Each gets `should_escalate=true`; no race conditions |
| Invalid webhook payload | `curl -X POST /webhooks/gmail -d '{}'` | Returns 422 Validation Error; does not crash |
| 404 customer ref | `customer_ref="UNKNOWN-9999"` | Auto-creates guest customer; processing continues |

### Stability verification after chaos

```bash
# After any chaos test, verify system recovery:
curl http://localhost:8000/health          # → {"status":"ok"}
curl http://localhost:8000/readiness       # → HTTP 200
pytest tests/test_api.py -v               # → 26 passed, 0 failures
```

---

## 6. What Is Simulated vs What Is Live

| Component | Demo / Default Mode | Live Production Mode | How to Switch |
|-----------|--------------------|--------------------|---------------|
| **OpenAI Agents SDK** | Rule-based fallback | Real GPT-4o calls | Set `OPENAI_API_KEY` |
| **Kafka** | In-memory mock broker | Confluent Cloud | `KAFKA_MOCK_MODE=false` + broker config |
| **Gmail sending** | Mock (logs to console) | Gmail API | Set `GMAIL_CREDENTIALS_JSON` |
| **WhatsApp sending** | Mock (logs to console) | Twilio API | Set `TWILIO_ACCOUNT_SID` + `TWILIO_AUTH_TOKEN` |
| **Database** | SQLite file | PostgreSQL (Neon/Supabase/Railway) | Set `DATABASE_URL=postgresql://...` |
| **Webhook signatures** | Not validated (no secret) | HMAC validation | Set `TWILIO_AUTH_TOKEN` |
| **CORS** | `localhost:3000` | Your Vercel URL | Set `CORS_ORIGINS` |

All mock modes are production-identical in terms of the API contract. The response shape, ticket creation, AI processing, and escalation logic behave identically whether OpenAI is live or rule-based.

---

## 7. 24-Hour Soak Test (Full Production)

To run a genuine 24-hour soak test with real services:

### Prerequisites

```bash
export DATABASE_URL="postgresql://..."          # Neon or Supabase
export OPENAI_API_KEY="sk-..."
export KAFKA_MOCK_MODE=false
export KAFKA_BOOTSTRAP_SERVERS="pkc-xxx.confluent.cloud:9092"
export KAFKA_SECURITY_PROTOCOL="SASL_SSL"
export KAFKA_SASL_MECHANISM="PLAIN"
export KAFKA_SASL_USERNAME="..."
export KAFKA_SASL_PASSWORD="..."
```

### Start and run

```bash
# API with multiple workers (PostgreSQL supports this)
uvicorn api.main:app --host 0.0.0.0 --port 8000 --workers 4

# 24h Locust soak
locust -f tests/load_test.py \
  --host=http://localhost:8000 \
  --users=20 \
  --spawn-rate=2 \
  --run-time=24h \
  --headless \
  --html=reports/soak-24h.html \
  --csv=reports/soak-24h
```

### Monitoring during test

```bash
# Every 30 minutes — check health and escalation rate
watch -n 1800 'curl -s http://localhost:8000/metrics/summary?hours=1 | python -m json.tool'

# Memory leak check
docker stats syncflow-api
```

### 24h Success Criteria

| Metric | Target |
|--------|--------|
| Uptime | 100% (zero unplanned restarts) |
| Error rate | < 1% of all requests |
| p95 latency | < 2000ms |
| Escalation rate | < 15% (healthy KB coverage) |
| Memory (RSS) | Stable over 24h — no upward trend |
| KB auto-resolution | > 70% of tickets resolved by AI without escalation |
| Dead-letter queue depth | < 0.5% of total events |
