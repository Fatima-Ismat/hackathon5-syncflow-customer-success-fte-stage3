# Testing Guide
## SyncFlow Customer Success Digital FTE — Stage 3

**Owner:** Ismat Fatima | **Hackathon 5 — Final Stage**

---

## Test Suite Summary

| File | Type | Count | What is tested |
|------|------|-------|---------------|
| `test_agent.py` | Unit | 34 | KB search (6 categories), sentiment (5 types), ticket creation, escalation routing, formatters, full agent pipeline |
| `test_channels.py` | Unit | 15 | Email normalize/send_reply, WhatsApp normalize/send_reply, Web Form normalize/send_reply, cross-channel normalization |
| `test_api.py` | Integration | 26 | All 19 endpoints: health, readiness, support submit, tickets CRUD, customers, webhooks, metrics |
| `test_multichannel_e2e.py` | E2E | 12 + 2 slow | Full pipeline flows: web form, email webhook, WhatsApp webhook, cross-channel continuity, escalation, metrics, 24h readiness burst |
| `load_test.py` | Load | Locust | `SupportFormUser`, `TicketLookupUser`, `WebhookSimulator` — 50-user profile |
| **Total** | | **96** | **All passing — 0 failures, 0 warnings** |

---

## Running Tests

### Prerequisites

```bash
pip install -r requirements.txt
# locust is only needed for load tests:
pip install locust
```

### Fast Local Tests (default — judge/demo ready)

```bash
# 94 core tests — no warnings, no Locust, no slow bursts
pytest -q
```

`pytest.ini` configures this automatically:
- `slow` and `load` markers excluded by default
- `DeprecationWarning` suppressed (Stage-2 `datetime.utcnow()` calls)
- `tests/load_test.py` not collected (prevents Locust monkey-patching noise)
- Windows `ThreadPoolExecutor` shutdown fix applied in `conftest.py`

### Include Slow Burst Tests

```bash
# 96 tests including the 10-request burst + post-load health check
pytest -m "not load" -v
```

### Run Specific Test Suites

```bash
# Agent unit tests only
pytest tests/test_agent.py -v

# Channel adapter tests only
pytest tests/test_channels.py -v

# API integration tests only
pytest tests/test_api.py -v

# E2E multi-channel tests only
pytest tests/test_multichannel_e2e.py -v

# Slow tests only (burst simulation)
pytest -m slow -v
```

### With Coverage Report

```bash
pytest -q --cov=. --cov-report=term-missing
pytest -q --cov=. --cov-report=html    # → htmlcov/index.html
```

### Run Load Tests (Locust — requires live API server)

```bash
# Start API first
uvicorn api.main:app --port 8000 &

# Interactive web UI at http://localhost:8089
locust -f tests/load_test.py --host=http://localhost:8000

# Headless (10 users, 30 seconds)
locust -f tests/load_test.py \
  --host=http://localhost:8000 \
  --users=10 --spawn-rate=2 --run-time=30s --headless

# Against Hugging Face deployment
locust -f tests/load_test.py \
  --host=https://ismat110-syncflow-api.hf.space \
  --users=20 --spawn-rate=4 --run-time=60s --headless \
  --html=load-report.html
```

---

## Test Categories

### Unit Tests (`test_agent.py`, `test_channels.py`)

No external services required. All tests use:
- `KAFKA_MOCK_MODE=true` (set in `conftest.py`)
- `DATABASE_URL=sqlite://` (in-memory, per test)
- `OPENAI_API_KEY=sk-test-mock-key-for-testing-only`

Key agent test patterns:
```python
# Calls _impl_* variants directly (avoids FunctionTool wrapping from SDK)
def _call_tool(func_name, *args, **kwargs):
    mod = importlib.import_module("agent.tools")
    fn = getattr(mod, f"_impl_{func_name}", None) or getattr(mod, func_name)
    return fn(*args, **kwargs)
```

### Integration Tests (`test_api.py`)

Uses `fastapi.testclient.TestClient` — no actual HTTP server needed. Covers:
- All endpoints with valid and invalid payloads
- HTTP status codes: 200, 400, 404, 422
- Response shapes: `{"success": true, "data": {...}}`
- Webhook acceptance (Gmail, WhatsApp Twilio format)
- Customer cross-channel lookup

### E2E Tests (`test_multichannel_e2e.py`)

Full pipeline simulation via TestClient. Tests 7 complete flows:

| Test class | Flow |
|-----------|------|
| `TestWebFormE2E` | Submit → ticket created → status lookup |
| `TestEmailE2E` | Gmail webhook → event accepted → direct API email |
| `TestWhatsAppE2E` | Twilio webhook → accepted; direct API WhatsApp |
| `TestCrossChannelContinuity` | Same customer ref on two channels; new customer auto-create |
| `TestEscalationE2E` | Angry message → auto-escalate; manual escalation API |
| `TestMetricsE2E` | Submit 3 tickets → metrics reflect activity; channel breakdown |
| `Test24HourReadiness` (**@slow**) | 10-request burst across all channels; health check after |

### Load Tests (`load_test.py`)

Three Locust `HttpUser` classes simulate realistic traffic:

| Class | Behavior | Task weights |
|-------|---------|-------------|
| `SupportFormUser` | Web form submissions (normal + escalating); health checks | 6:2:1:3 |
| `TicketLookupUser` | Ticket listing, metrics, customer profiles, 404 testing | 4:2:2:1:3:1 |
| `WebhookSimulator` | Gmail and WhatsApp webhook events | 3:2 |

---

## Performance Targets

| Metric | Target | Measurement |
|--------|--------|-------------|
| API response time (p50) | < 500ms | Locust report |
| API response time (p95) | < 2000ms | Locust report |
| API response time (p99) | < 5000ms | Locust report |
| Throughput (normal load: 10 users) | > 10 req/s | Locust report |
| Error rate | < 1% | Locust report |
| Health check latency | < 50ms | `curl -w "%{time_total}"` |
| KB search time | < 100ms | Unit test timing |
| Escalation decision | < 50ms | Unit test timing |
| Full pipeline (web form) | < 3000ms | Integration test timing |

---

## Test Coverage Map

| Component | Covered by |
|-----------|-----------|
| `agent/tools.py` | `test_agent.py` — KB search (6 categories), sentiment (5 types), ticket creation, escalation routing (3 queues), customer lookup |
| `agent/customer_success_agent.py` | `test_agent.py` — full pipeline, 3 channels, escalation detection, confidence scoring |
| `agent/formatters.py` | `test_agent.py` — email format, WhatsApp conciseness (<80 words), web form ref inclusion |
| `channels/email_channel.py` | `test_channels.py` — normalize (from_email, body, subject, missing fields), send_reply signature |
| `channels/whatsapp_channel.py` | `test_channels.py` — Twilio format, simplified format, phone normalization, send_reply |
| `channels/web_form_channel.py` | `test_channels.py` — full form, minimal form, message extraction, send_reply |
| `api/main.py` — all 19 endpoints | `test_api.py`, `test_multichannel_e2e.py` |
| 9-stage pipeline | `test_multichannel_e2e.py` — 7 complete E2E flows |
| Escalation routing | `test_agent.py`, `test_api.py::test_escalation_triggered_for_angry_customer`, `TestEscalationE2E` |
| Kafka mock broker | `test_api.py::TestHealthEndpoints::test_health_includes_kafka_status` |
| Cross-channel identity | `TestCrossChannelContinuity`, `test_api.py::TestCustomerEndpoints` |
| Load resilience | `Test24HourReadiness` (burst), `load_test.py` (Locust) |

---

## Marker Reference

| Marker | Description | Include in run |
|--------|-------------|----------------|
| _(none)_ | Core unit + integration + E2E tests | `pytest -q` (default) |
| `@pytest.mark.slow` | Long-running burst simulation tests | `pytest -m slow` |
| `@pytest.mark.load` | Locust file test — requires `locust` installed | `pytest -m load` or `locust -f` |

Configure in `pytest.ini`:
```ini
addopts = -m "not slow and not load" --ignore=tests/load_test.py --tb=short
```

---

## CI/CD Integration

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: "3.11"
      - run: pip install -r requirements.txt pytest pytest-cov
      - run: pytest -q --cov=.
        env:
          KAFKA_MOCK_MODE: "true"
          DATABASE_URL: "sqlite://"
          OPENAI_API_KEY: "sk-test-mock"
```

---

## 24-Hour Readiness Simulation Plan

For a full production soak test:

### 1. Setup

```bash
# Use real Kafka and PostgreSQL for the soak
export DATABASE_URL="postgresql://..."
export KAFKA_MOCK_MODE=false
export KAFKA_BOOTSTRAP_SERVERS="pkc-xxx.confluent.cloud:9092"
export OPENAI_API_KEY="sk-..."

uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### 2. Run 24h Soak Test

```bash
locust -f tests/load_test.py \
  --host=http://localhost:8000 \
  --users=20 \
  --spawn-rate=2 \
  --run-time=24h \
  --headless \
  --html=reports/soak-24h.html \
  --csv=reports/soak-24h
```

### 3. Monitor During Test

```bash
# Every 30 minutes check health and metrics
watch -n 1800 'curl -s http://localhost:8000/metrics/summary?hours=1 | python -m json.tool'

# Real-time escalation rate
curl http://localhost:8000/metrics/summary | jq .data.escalation_rate

# Memory / CPU (local)
docker stats syncflow-api
```

### 4. Success Criteria

| Metric | Target |
|--------|--------|
| Uptime | 100% (zero restarts) |
| Error rate | < 1% |
| p95 latency | < 2000ms |
| Escalation rate | < 15% |
| Memory (RSS) | Stable over 24h (no leak) |
| KB resolution rate | > 70% of tickets resolved by AI |
