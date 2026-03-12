# Operations Runbook
## SyncFlow Customer Success Digital FTE — Stage 3

**Owner:** Ismat Fatima | **Last Updated:** 2025

---

## 1. Service Overview

| Service | Role | Port | Health Check |
|---------|------|------|-------------|
| `syncflow-api` | FastAPI REST API + 9-stage pipeline | 8000 / 7860 (HF) | `GET /health` |
| `syncflow-worker` | Kafka message processor | — | process alive check |
| `syncflow-metrics` | Metrics aggregation | — | process alive check |
| PostgreSQL | CRM data store | 5432 | `pg_isready` |
| Kafka | Event streaming | 9092 | broker API |
| Next.js Frontend | Web UI | 3000 / 443 (Vercel) | HTTP 200 |

### Fallback Behaviour Summary

| Dependency | Failure | Automatic Fallback |
|------------|---------|-------------------|
| OpenAI API | Quota / network | Rule-based KB matching + template response |
| Kafka broker | Unreachable | In-memory thread-safe mock broker |
| PostgreSQL | Connection error | SQLite in-memory (`DATABASE_URL=sqlite://`) |
| Channel send | Gateway error | Ticket created; `delivery_status="failed"` logged |

---

## 2. Incident Response Playbook

### 2.1 API Down

**Symptoms:** `GET /health` returns non-200 or times out; webhooks fail

**Immediate diagnostic:**
```bash
# Hugging Face Spaces
curl -s https://YOUR-API.hf.space/health | python -m json.tool

# Docker local
docker logs syncflow-api --tail 50

# Kubernetes
kubectl logs -n syncflow -l app=syncflow-api --tail 50
kubectl describe pod -n syncflow -l app=syncflow-api
```

**Recovery steps:**
1. Check if OOM killed: look for `"memory limit exceeded"` in logs
2. Verify dependencies: DB, Kafka
3. Restart container
   - HF Spaces: push any commit to trigger rebuild
   - K8s: `kubectl rollout restart deployment syncflow-api -n syncflow`
4. If persistent: roll back to previous image

**Escalation:** If down > 5 minutes, flag to on-call engineer.

---

### 2.2 Database Outage

**Symptoms:** 500 errors on ticket creation; customer lookup returns 404 for known refs

**Automatic fallback:**
- System switches to in-memory CRM (tickets exist for session duration only)
- New tickets are still created (in-memory, lost on restart)
- Existing DB tickets cannot be retrieved until connection restores

**Diagnostic:**
```bash
# Test DB connection
psql "$DATABASE_URL" -c "SELECT 1;"

# Check Neon / Supabase status page for outage notice
```

**Emergency SQLite fallback:**
```bash
export DATABASE_URL="sqlite:///./syncflow_emergency.db"
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

**Recovery:**
```bash
# Verify migration is current
psql "$DATABASE_URL" -c "\dt"

# Re-seed if tables are missing
python database/seed.py

# Replay missed messages from Kafka dead-letter (see §3.3)
```

---

### 2.3 Kafka Outage

**Symptoms:** Events not appearing in metrics; worker logs show connection errors

**Automatic fallback:**
- `KAFKA_MOCK_MODE` auto-activates when broker is unreachable
- All events go to in-memory deque (cleared on restart)
- API continues processing normally; messages are not lost within the session

**Force mock mode:**
```bash
export KAFKA_MOCK_MODE=true
# Restart workers
```

**Recovery:**
```bash
# Verify Kafka is reachable (Confluent Cloud: check status.confluent.io)
kafka-broker-api-versions --bootstrap-server $KAFKA_BOOTSTRAP_SERVERS

# Re-enable real Kafka
export KAFKA_MOCK_MODE=false
# Restart workers
```

---

### 2.4 Webhook Failures

**Symptoms:** Gmail or WhatsApp messages not being processed; customers not receiving replies

**Gmail webhook diagnostic:**
```bash
# Manual test — should return {"status":"accepted","channel":"email"}
curl -X POST https://YOUR-API.hf.space/webhooks/gmail \
  -H "Content-Type: application/json" \
  -d '{"from_email":"test@test.com","subject":"Test","body":"Test message"}'
```

**WhatsApp webhook diagnostic:**
```bash
# Manual Twilio format test — should return {"status":"accepted"}
curl -X POST https://YOUR-API.hf.space/webhooks/whatsapp \
  -d "From=whatsapp:+14155550101&Body=Test message&MessageSid=SM123456"
```

**Common fixes:**

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| 404 on webhook URL | Wrong URL in Twilio/Google config | Update webhook URL |
| 403 Signature invalid | `TWILIO_AUTH_TOKEN` mismatch | Verify token in Twilio Console |
| 202 but no processing | BackgroundTask exception | Check logs for traceback |
| API sleeping (HF) | Free tier 48h sleep | Implement keep-alive or upgrade tier |

---

### 2.5 High Escalation Rate

**Symptoms:** `GET /metrics/summary` shows `escalation_rate > 0.3`

**Investigation:**
```bash
# Escalation breakdown
curl -s https://YOUR-API.hf.space/metrics/summary?hours=24 | python -m json.tool

# Recent escalated tickets
curl "https://YOUR-API.hf.space/tickets?status=escalated&limit=20"
```

**Root causes and fixes:**

| Root Cause | Detection | Action |
|-----------|-----------|--------|
| KB coverage gap | Many `low_kb_confidence` escalations | Add KB articles for top unresolved topics |
| Angry customer spike | Many `high_anger_score` escalations | Review if caused by external event (outage, billing cycle) |
| Threshold too low | High escalation rate, low anger scores | Adjust confidence threshold in `agent/tools.py` |
| Trending issue | Cluster of same topic | Check if product bug/incident is causing support surge |

---

### 2.6 AI Agent Low Confidence / Generic Responses

**Symptoms:** All responses generic; `kb_confidence < 0.3` on most tickets

**Check:**
```bash
# Test agent directly (no API key required — uses fallback)
python -c "
from agent.customer_success_agent import process_customer_message
r = process_customer_message('web_form', 'C-1042', 'How do I reset my password?')
print(r)
"
```

**Recovery:**
- If OpenAI quota exhausted: system uses rule-based fallback automatically (check logs for `"fallback mode"`)
- Top up OpenAI credits or wait for quota reset
- Verify `OPENAI_API_KEY` in secrets/env

---

## 3. Manual Procedures

### 3.1 Manually Escalate a Ticket

```bash
curl -X POST https://YOUR-API.hf.space/tickets/TKT-XXXXXXXX/escalate \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "high_anger_score",
    "priority": "high",
    "notes": "VIP customer, waiting 48h, needs immediate attention"
  }'
```

Valid reason codes: `high_anger_score`, `low_kb_confidence`, `legal_threat`, `security_breach`, `churn_risk`, `billing_dispute`, `vip_customer`, `manual_review`.

### 3.2 Resolve a Ticket

```bash
curl -X POST https://YOUR-API.hf.space/tickets/TKT-XXXXXXXX/resolve \
  -H "Content-Type: application/json" \
  -d '{"resolution_notes": "Issue resolved via KB article on data export"}'
```

### 3.3 Replay Dead-Letter Events

```bash
# View dead-letter events (mock mode)
python -c "
from kafka_client import get_recent_events, TOPICS
events = get_recent_events(TOPICS['DEAD_LETTER'])
for e in events:
    print(e)
"

# Replay events by resubmitting
python -c "
import requests, json
events = [...]  # from above
for e in events:
    r = requests.post('http://localhost:8000/support/submit', json={
        'channel': e.get('channel', 'web_form'),
        'customer_ref': e.get('customer_ref', 'unknown'),
        'message': e.get('payload', {}).get('message', ''),
    })
    print(r.status_code, r.json().get('data', {}).get('ticket_ref'))
"
```

### 3.4 Re-Seed Database

```bash
# Development (SQLite)
python database/seed.py

# Production (PostgreSQL)
DATABASE_URL="postgresql://..." python database/seed.py
```

---

## 4. Monitoring and Alert Strategy

### 4.1 Key Health Metrics

```bash
# Full system health (all subsystems)
curl -s https://YOUR-API.hf.space/health | python -m json.tool
# Expected: {"status":"ok","version":"3.0.0","services":{"api":"ok","crm":"ok","kafka":"..."}}

# 24-hour performance summary
curl -s "https://YOUR-API.hf.space/metrics/summary?hours=24" | python -m json.tool

# Per-channel breakdown
curl -s "https://YOUR-API.hf.space/metrics/channels?hours=24" | python -m json.tool

# Sentiment distribution
curl -s "https://YOUR-API.hf.space/metrics/sentiment?hours=24" | python -m json.tool
```

### 4.2 Alert Thresholds

| Metric | Warning | Critical | Response |
|--------|---------|----------|----------|
| Escalation rate | > 20% | > 35% | Review KB, check for product incident |
| KB confidence avg | < 0.5 | < 0.3 | Add KB articles for top missing topics |
| API p95 latency | > 1500ms | > 3000ms | Scale pods, check agent response time |
| API error rate | > 0.5% | > 2% | Check logs, investigate root cause |
| Health check | Any failure | Repeated failure | K8s auto-restart; escalate if persistent |
| SLA breach (Critical) | 30m remaining | Breached | Manual escalation immediately |
| SLA breach (High) | 1h remaining | Breached | Manual escalation |

### 4.3 Ticket Queue Monitoring

```bash
# Open tickets (needs processing)
curl "https://YOUR-API.hf.space/tickets?status=open&limit=50"

# Escalated tickets (needs human)
curl "https://YOUR-API.hf.space/tickets?status=escalated&limit=20"

# Critical open tickets (SLA risk)
curl "https://YOUR-API.hf.space/tickets?status=open&priority=critical&limit=10"
```

### 4.4 Recommended Monitoring Schedule

| Frequency | Action |
|-----------|--------|
| Every 5 minutes | `GET /health` liveness check |
| Every 30 minutes | Review `GET /metrics/summary?hours=1` |
| Every 4 hours | Review escalated ticket queue |
| Daily | Review 24h metrics: escalation rate, KB confidence, channel volumes |
| Weekly | Review KB coverage, add articles for top unresolved topics |

---

## 5. Retry and Failure Behaviour

| Component | Retry Policy |
|-----------|-------------|
| Kafka publish | 3 retries → falls back to mock broker → event to dead-letter |
| Webhook processing | Single attempt in BackgroundTask; failure logged to dead-letter |
| AI Agent | 1 retry → falls back to rule-based response |
| DB operations | No auto-retry; exception propagated; fallback to in-memory |
| WhatsApp delivery | Twilio handles delivery retries (3×) |
| Gmail send | Mock mode: no retry; real Gmail API: built-in exponential backoff |

---

## 6. SLA Breach Response

SLA deadlines are set at ticket creation time based on customer plan and priority.

**SLA matrix (hours to first response):**

| Plan | Critical | High | Medium | Low |
|------|---------|------|--------|-----|
| Starter | 4h | 12h | 24h | 48h |
| Growth | 2h | 6h | 12h | 24h |
| Business | 1h | 2h | 4h | 8h |
| Enterprise | 30m | 1h | 2h | 4h |

**Response procedure:**
1. Identify near-breach tickets: `GET /tickets?status=open&priority=critical`
2. Check if AI response was already sent (`GET /tickets/{ref}`)
3. If no response sent: `POST /tickets/{ref}/escalate` to route to human agent
4. Notify customer proactively if SLA missed
5. Log the breach in the metrics system

---

## 7. Rollback Procedure

### Hugging Face Spaces

```bash
# View history
git log --oneline

# Revert to last good commit
git revert HEAD && git push

# Hard rollback (use carefully)
git reset --hard COMMIT_SHA && git push --force
```

### Vercel Frontend

1. Vercel Dashboard → Deployments
2. Find last good deployment → `...` → Redeploy → Promote to Production

### Kubernetes

```bash
# View rollout history
kubectl rollout history deployment syncflow-api -n syncflow

# Rollback to previous version
kubectl rollout undo deployment syncflow-api -n syncflow

# Rollback to specific revision
kubectl rollout undo deployment syncflow-api --to-revision=2 -n syncflow
```

---

## 8. Common Error Reference

| Error message | Cause | Fix |
|---------------|-------|-----|
| `Invalid channel 'X'` | Wrong channel name | Use: `email`, `whatsapp`, `web_form` |
| `Ticket not found: TKT-XXXX` | Ticket missing from DB | Check `DATABASE_URL`; DB may have reset |
| `Customer not found: C-XXXX` | Unknown ref | Submit without `customer_ref` to auto-create |
| `psycopg2.OperationalError` | PostgreSQL unreachable | Check `DATABASE_URL`; set SQLite fallback |
| `Kafka publish error` | Kafka unreachable | Set `KAFKA_MOCK_MODE=true`; restart |
| `429 Too Many Requests` | OpenAI rate limit | Add retry backoff; rule-based fallback activates |
| `identify_customer() got unexpected keyword` | API version mismatch | Update `api/main.py` to use correct CRM signature |
| `FunctionTool not callable` | Using SDK object directly | Use `_impl_*` variants in orchestration code |
