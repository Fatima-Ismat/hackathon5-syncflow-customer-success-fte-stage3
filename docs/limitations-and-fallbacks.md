# Limitations and Fallbacks
## SyncFlow Customer Success Digital FTE — Stage 3

**Owner:** Ismat Fatima | **Hackathon 5 — Stage 3 Final**

> This document is included as a transparency statement for judges.
> Every listed limitation has a documented fallback. The demo works completely without any external credentials.

---

## 1. Gmail / Email — Live Sending

### Current status
Gmail live sending is **simulated** in default mode. When `GMAIL_CREDENTIALS_JSON` is not set, the `send_reply()` method in `channels/email_channel.py` logs the outgoing message to console instead of sending via the Gmail API.

### What still works
- Gmail **inbound** webhook (`POST /webhooks/gmail`) — fully processes incoming emails through the 9-stage pipeline
- Ticket creation, AI response generation, escalation routing — all happen normally
- The response text that would be sent is visible in the API response and logs
- All 15 channel adapter tests and 26 API integration tests pass regardless

### Fallback behavior
```python
# channels/email_channel.py
def send_reply(to_email, to_name, subject, body, thread_id=None):
    if not GMAIL_CREDENTIALS:
        logger.info(f"[MOCK] Email to {to_email}: {body[:100]}...")
        return {"sent": False, "mock": True}
    # real Gmail API call here
```

### Production path
```bash
# Provide OAuth credentials as JSON
GMAIL_CREDENTIALS_JSON='{"installed":{"client_id":"...","client_secret":"..."}}'
# Or provide an SMTP configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-email@gmail.com
SMTP_PASSWORD=app-specific-password
```

---

## 2. WhatsApp / Twilio — Sandbox Limitation

### Current status
WhatsApp live sending is **simulated** in default mode. Without `TWILIO_ACCOUNT_SID` and `TWILIO_AUTH_TOKEN`, the `send_reply()` method in `channels/whatsapp_channel.py` logs the outgoing message.

WhatsApp **inbound** webhook verification (Twilio HMAC signature) is skipped when `TWILIO_AUTH_TOKEN` is not set. In production, all webhooks must have a valid Twilio signature.

### What still works
- WhatsApp inbound webhook (`POST /webhooks/whatsapp`) — processes Twilio form-encoded payloads
- Phone normalization to E.164 format
- Cross-channel identity resolution via phone number
- Escalation and ticket creation
- All channel adapter tests pass

### Twilio Sandbox note
Twilio WhatsApp sandbox requires:
- Users to opt-in by sending a join message to the sandbox number
- Not suitable for unsolicited outbound messages
- For production: apply for a dedicated WhatsApp Business number through Twilio

### Fallback behavior
```python
# channels/whatsapp_channel.py
def send_reply(to_phone, body):
    if not TWILIO_CLIENT:
        logger.info(f"[MOCK] WhatsApp to {to_phone}: {body[:100]}...")
        return {"sent": False, "mock": True}
    # real Twilio API call here
```

### Production path
```bash
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_WHATSAPP_FROM=whatsapp:+14155238886   # Twilio sandbox or dedicated number
```

---

## 3. Kafka — In-Memory Mock Mode

### Current status
Kafka is running in **in-memory mock mode** by default (`KAFKA_MOCK_MODE=true`). The `MockKafkaBroker` class in `kafka_client.py` is a thread-safe `deque` that mimics the Kafka producer/consumer API without any network connections.

### What still works
- All 8 topics are created and events are published
- Topic-based routing logic is identical to real Kafka
- Dead-letter queue pattern works (events go to `fte.dead-letter` on failure)
- Workers can consume from mock broker
- All tests pass with mock mode

### Differences from real Kafka
| Feature | Mock Mode | Real Kafka |
|---------|-----------|-----------|
| Persistence | In-memory (lost on restart) | Durable (configurable retention) |
| Distribution | Single-process only | Multi-process / multi-host |
| Consumer groups | Not implemented | Full partition/offset management |
| Replay | Not supported | Seek to offset |
| Throughput | Unlimited (in-memory) | Network-bound |

### Production path
```bash
KAFKA_MOCK_MODE=false
KAFKA_BOOTSTRAP_SERVERS=pkc-xxx.us-east-1.aws.confluent.cloud:9092
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=YOUR_CONFLUENT_API_KEY
KAFKA_SASL_PASSWORD=YOUR_CONFLUENT_API_SECRET
```

---

## 4. PostgreSQL — SQLite Fallback

### Current status
When `DATABASE_URL` is not set (or is set to `sqlite://...`), the system uses **SQLite**. All 8 database tables are created identically in SQLite via SQLAlchemy 2.0's ORM.

### What still works
- Full CRUD for customers, tickets, messages, knowledge base, metrics
- SLA deadline calculation and ticket state machine
- Cross-channel identity resolution
- All 96 tests pass against SQLite
- Seed data loads correctly

### SQLite limitations in production
| Limitation | Impact |
|------------|--------|
| Single writer | Only `WORKERS=1` safe (concurrent writes cause locking) |
| No persistence on HF Spaces rebuild | Data lost when Space is rebuilt from scratch |
| No connection pooling | Not suitable for > 10 concurrent users |
| No full-text search | KB search uses LIKE matching instead of pg_trgm |

### Production path
```bash
# Neon (free tier — recommended)
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/syncflow_crm?sslmode=require

# Supabase
DATABASE_URL=postgresql://postgres:password@db.xxx.supabase.co:5432/postgres

# Railway
DATABASE_URL=postgresql://postgres:password@monorail.proxy.rlwy.net:PORT/railway
```

---

## 5. OpenAI Agents SDK — Rule-Based Fallback

### Current status
The OpenAI Agents SDK is **optional**. When `OPENAI_API_KEY` is not set (or is invalid), `agent/tools.py` activates the `_impl_*` plain-Python fallback variants:

| Tool | With OpenAI | Without OpenAI (fallback) |
|------|-------------|--------------------------|
| `search_kb` | Semantic search via GPT | Keyword + category matching |
| `analyze_sentiment` | LLM-based nuance detection | Rule-based anger/urgency keywords |
| `create_ticket` | Unchanged (pure CRM) | Unchanged |
| `escalate_ticket` | Unchanged | Unchanged |
| `get_customer_info` | Unchanged | Unchanged |

### Fallback activation
```python
# agent/tools.py
def _impl_search_kb(query: str, category: str = None) -> dict:
    # Pure Python — no OpenAI call
    # Uses keyword matching against knowledge_base table
    ...
```

### Quality difference
- Rule-based responses are shorter and less nuanced than GPT-4o
- KB confidence scores tend to be lower (0.4–0.7 vs 0.7–0.95)
- Escalation logic is identical — rule-based detection still triggers correctly
- All tests use the rule-based fallback and pass

### Production path
```bash
OPENAI_API_KEY=sk-...
# Optional model override (default: gpt-4o-mini for speed/cost)
OPENAI_MODEL=gpt-4o
```

---

## 6. HF Spaces Free Tier — Cold Start

### Current status
Hugging Face Spaces free tier puts Spaces to sleep after 48 hours of inactivity. The first request after sleep takes approximately **30 seconds** while the container starts.

### Impact
- Demo URLs shared in submission may be slow on first load
- Not suitable for 24/7 SLA requirements without upgrade

### Mitigation options
| Option | Cost | How |
|--------|------|-----|
| Keep-alive ping | Free | External cron job: `curl -s HF_URL/health` every 30min |
| Persistent Space | Paid ($9/mo) | HF Spaces Pro plan |
| Railway.app | Free tier | Alternative Docker hosting |
| Fly.io | Free tier | `fly launch` from `Dockerfile` |

### Not a demo issue
For the hackathon demo, the cold start is acceptable. The `/health` endpoint will respond once warm, confirming the system is running.

---

## 7. Frontend Real-Time Updates

### Current status
The admin dashboard polls for data every 30 seconds. There is no WebSocket or Server-Sent Events connection.

### Impact
- Ticket status changes visible within 30s, not instantly
- Not suitable for live operations centers requiring sub-second updates

### Production path
```typescript
// Add SSE endpoint to FastAPI:
// GET /stream/metrics  →  EventSource in frontend
// GET /stream/tickets  →  real-time ticket updates
```

---

## Summary

| Component | Demo Mode | Fully Production-Ready? | Activation |
|-----------|-----------|------------------------|-----------|
| Web Form channel | ✅ Live (no mock) | ✅ | No change needed |
| Gmail inbound | ✅ Live (processes webhooks) | ✅ | No change needed |
| Gmail outbound | 🔶 Mock (logs) | With credentials | Set `GMAIL_CREDENTIALS_JSON` |
| WhatsApp inbound | ✅ Live (processes webhooks) | ✅ | No change needed |
| WhatsApp outbound | 🔶 Mock (logs) | With credentials | Set Twilio secrets |
| OpenAI AI agent | 🔶 Rule-based fallback | With API key | Set `OPENAI_API_KEY` |
| Kafka | 🔶 In-memory mock | With broker | Set `KAFKA_MOCK_MODE=false` |
| Database | 🔶 SQLite | With PostgreSQL | Set `DATABASE_URL=postgresql://...` |
| Ticket system | ✅ Live | ✅ | No change needed |
| Escalation routing | ✅ Live | ✅ | No change needed |
| SLA management | ✅ Live | ✅ | No change needed |
| Metrics API | ✅ Live | ✅ | No change needed |
| REST API (19 endpoints) | ✅ Live | ✅ | No change needed |
| Frontend | ✅ Live | ✅ | No change needed |
