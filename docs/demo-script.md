# Demo Script — 2-Minute Judge Walkthrough
## SyncFlow Customer Success Digital FTE — Stage 3

**Owner:** Ismat Fatima | **Hackathon 5 — Stage 3 Final**

---

## Pre-Demo Setup (do this before the demo)

```bash
# Terminal 1 — Start backend (zero config, no credentials needed)
cd Hackathon5-Customer-Success-FTE-Stage3
pip install -r requirements.txt   # first time only
python database/seed.py           # loads 7 demo customers + 12 KB articles
uvicorn api.main:app --reload --port 8000

# Terminal 2 — Start frontend
cd frontend
npm install                        # first time only
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
npm run dev

# Verify both are running:
# API:      http://localhost:8000/docs
# Frontend: http://localhost:3000
```

Have two browser tabs pre-opened:
- Tab A: `http://localhost:8000/docs` (Swagger UI)
- Tab B: `http://localhost:3000` (Frontend)
- Tab C: Terminal ready with curl commands below

---

## 2-Minute Demo Flow

### [0:00 – 0:15] Show the architecture (15 seconds)

**Say:** *"SyncFlow is a 24/7 AI Customer Success agent that handles support across Gmail, WhatsApp, and Web Form. It uses OpenAI Agents SDK with a 9-stage processing pipeline backed by PostgreSQL and Kafka."*

**Show:** README architecture diagram or `docs/architecture.md` briefly.

---

### [0:15 – 0:35] Standard ticket — web form channel (20 seconds)

**Tab C — run this:**

```bash
curl -s -X POST http://localhost:8000/support/submit \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "web_form",
    "customer_ref": "C-1042",
    "name": "Alice Chen",
    "email": "alice@acmecorp.com",
    "subject": "Cannot export data",
    "message": "I am trying to export my workflow data to CSV but the download button is greyed out."
  }' | python -m json.tool
```

**What to point out in the response:**
- `ticket_ref` — unique reference (format `TKT-YYYYMMDD-XXXX`)
- `ai_response` — AI's answer (from KB article on data export)
- `confidence_score` — e.g., `0.87`
- `kb_section` — shows which KB category answered it
- `should_escalate: false` — normal ticket, no escalation needed

**Say:** *"The 9-stage pipeline normalized the web form input, identified the customer in the CRM, ran the OpenAI agent tool against the knowledge base, and created a ticket — all in under 500ms."*

---

### [0:35 – 0:55] Auto-escalation — angry customer (20 seconds)

**Tab C — run this:**

```bash
curl -s -X POST http://localhost:8000/support/submit \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "web_form",
    "customer_ref": "C-4459",
    "message": "This is UNACCEPTABLE! I have been waiting 3 weeks and nobody responds. I want a full refund or I will contact my lawyer immediately!"
  }' | python -m json.tool
```

**What to point out:**
- `should_escalate: true`
- `escalation_reason` — e.g., `legal_threat` or `extreme_dissatisfaction`
- `escalation_queue` — e.g., `legal-compliance` or `senior-support`
- `anger_score` — high value (> 0.8)
- `priority: "critical"` — auto-set by sentiment

**Say:** *"Sentiment analysis detected a legal threat and extreme anger. The ticket was automatically routed to the legal-compliance queue with critical priority — no human triage needed."*

---

### [0:55 – 1:10] Webhook channel — simulated Gmail (15 seconds)

**Tab C — run this:**

```bash
curl -s -X POST http://localhost:8000/webhooks/gmail \
  -H "Content-Type: application/json" \
  -d '{
    "from_email": "bob@techstartup.io",
    "subject": "API rate limit issue",
    "body": "Hi, we are hitting rate limits on your API endpoint. Our plan is Growth. Can you help?"
  }' | python -m json.tool
```

**What to point out:**
- HTTP 200 response with `"accepted": true` — webhook returns immediately
- Processing happens in `BackgroundTasks` (non-blocking)
- Email channel normalized same as web form — same agent, same CRM

**Say:** *"Gmail webhooks return 200 immediately and process asynchronously. All three channels share the same AI agent, CRM, and Kafka event bus."*

---

### [1:10 – 1:25] Cross-channel identity + metrics (15 seconds)

**Tab A (Swagger) or Tab C:**

```bash
# Ticket list
curl -s http://localhost:8000/tickets | python -m json.tool

# Customer cross-channel lookup
curl -s -X POST http://localhost:8000/customers/lookup \
  -H "Content-Type: application/json" \
  -d '{"email": "alice@acmecorp.com"}' | python -m json.tool

# Metrics summary
curl -s "http://localhost:8000/metrics/summary?hours=1" | python -m json.tool
```

**What to point out on metrics:**
- `tickets_created`, `responses_generated`, `escalations`
- `auto_resolution_rate` — percentage handled by AI
- `kb_usage_rate`
- `avg_agent_confidence`

**Say:** *"One customer identity across all channels. Full metrics with windowed aggregation — pluggable into any monitoring dashboard."*

---

### [1:25 – 1:40] Frontend live demo (15 seconds)

**Switch to Tab B (Frontend — http://localhost:3000):**

1. Show **Home page** — three cards: Submit, Track, Dashboard
2. Click **Submit a Request** → fill in the form → submit
3. Note the ticket reference shown in the success state
4. Click **Track Ticket** → paste the reference → show ticket detail
5. Click **Dashboard** → show live metrics (total tickets, escalation rate, channel breakdown)

**Say:** *"The Next.js 14 frontend connects to the same API. Metrics auto-refresh every 30 seconds."*

---

### [1:40 – 1:55] Test suite (15 seconds)

**Tab C — run:**

```bash
pytest -q
```

**Expected output:**
```
94 passed, 2 deselected, 0 warnings in ~21s
```

**Say:** *"96 tests: 34 agent unit tests, 15 channel adapter tests, 26 API integration tests, 14 E2E multi-channel tests, and a Locust load test. Zero warnings. Runs in 21 seconds."*

---

### [1:55 – 2:00] Close

**Say:** *"SyncFlow handles production-grade customer success across three channels with full fallback chains — no credentials required for this demo. The system is deployed on Hugging Face Spaces and Vercel. Thank you."*

---

## Backup Commands (if live demo has issues)

```bash
# Health check (should always work)
curl http://localhost:8000/health

# Readiness probe
curl http://localhost:8000/readiness

# List knowledge base articles
curl http://localhost:8000/tickets?limit=5

# WhatsApp webhook (Twilio format)
curl -s -X POST http://localhost:8000/webhooks/whatsapp \
  -d "From=whatsapp:+14155551042&Body=I+need+help+with+my+account&To=whatsapp:+14155550000"
```

---

## Key Numbers to Mention

| Fact | Value |
|------|-------|
| Processing stages | 9 |
| API endpoints | 19 |
| Test count | 96 (94 fast + 2 slow) |
| Knowledge base categories | 12 |
| Escalation reason codes | 17 |
| Specialist escalation queues | 8 |
| Database tables | 8 |
| Kafka topics | 8 |
| SLA tiers | 4 plans × 4 priorities = 16 SLA levels |
| Demo time with zero credentials | < 2 minutes |

---

## Recommended Screen Layout for Recording

```
┌─────────────────────────┬─────────────────────────┐
│                         │                         │
│   Browser: Frontend     │   Terminal: curl cmds   │
│   localhost:3000        │   + pytest output       │
│                         │                         │
├─────────────────────────┤                         │
│                         │                         │
│   Browser: Swagger UI   │                         │
│   localhost:8000/docs   │                         │
│                         │                         │
└─────────────────────────┴─────────────────────────┘
```
