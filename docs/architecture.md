# Architecture Document
## SyncFlow Customer Success Digital FTE — Stage 3

**Owner:** Ismat Fatima | **Hackathon 5 — Final Stage**

---

## System Overview

SyncFlow Customer Success Digital FTE is a production-grade AI-powered support platform operating 24/7 across three inbound channels (Gmail, WhatsApp, Web Form). Every inbound message — regardless of channel — passes through a deterministic 9-stage pipeline before a response is dispatched.

**Core design principles:**
- **Channel-agnostic pipeline:** one processing path for all channels
- **Graceful degradation:** every dependency (OpenAI, Kafka, PostgreSQL) has a fallback
- **Async-first:** webhooks return immediately; processing is non-blocking
- **Immutable audit trail:** every event published to Kafka; dead-letter queue for failures

---

## Full Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────┐
│                         INBOUND CHANNELS                                  │
│                                                                           │
│   📧 Gmail (Pub/Sub Push)    💬 WhatsApp (Twilio)    🌐 Web Form (REST) │
│   POST /webhooks/gmail       POST /webhooks/whatsapp  POST /support/submit│
└──────────────┬──────────────────────┬───────────────────────┬────────────┘
               │                      │                       │
               └──────────────────────▼───────────────────────┘
                                      │
┌─────────────────────────────────────▼─────────────────────────────────────┐
│                   FastAPI API Layer  (api/main.py)                         │
│                                                                            │
│  19 endpoints · Pydantic v2 validation · Swagger /docs · CORS configured  │
│  BackgroundTasks for async webhook processing (immediate HTTP 200 return)  │
└─────────────────────────────────────┬──────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼──────────────────────────────────────┐
│              9-Stage Message Processing Pipeline  (_process_message)        │
│                                                                             │
│  Stage 1  Validate channel name and minimum payload requirements            │
│  Stage 2  Normalize via channel adapter                                     │
│           email_channel / whatsapp_channel / web_form_channel               │
│  Stage 3  Identify customer  (4-strategy resolver)                          │
│           ref match → email lookup → phone lookup → auto-create guest       │
│  Stage 4  AI Agent run  (OpenAI Agents SDK or rule-based fallback)         │
│  Stage 5  Sentiment analysis  (anger / frustration / urgency scoring)       │
│  Stage 6  Create ticket  (SLA deadline: 4 plans × 4 priorities)            │
│  Stage 7  Escalation routing  (17 codes → 8 specialist queues)             │
│  Stage 8  Dispatch response via channel adapter send_reply()                │
│  Stage 9  Publish Kafka event + record metrics                              │
└──────────────┬───────────────────────────┬──────────────────────┬──────────┘
               │                           │                      │
               ▼                           ▼                      ▼
┌──────────────────────┐   ┌───────────────────────┐   ┌─────────────────────┐
│  AI Agent  agent/     │   │  CRM Layer  crm/      │   │  Kafka  kafka_client│
│                       │   │                       │   │                     │
│  OpenAI Agents SDK    │   │  ticket_service       │   │  8 topics:          │
│  OR rule-based        │   │  · State machine      │   │  fte.tickets.inc    │
│  (always available)   │   │  · SLA matrix         │   │  fte.email.in/out   │
│                       │   │  · Escalation routing │   │  fte.wa.in/out      │
│  @function_tool +     │   │                       │   │  fte.metrics        │
│  _impl_* fallbacks    │   │  customer_service     │   │  fte.escalations    │
│                       │   │  · 4-strategy ID      │   │  fte.dead-letter    │
│  Tools:               │   │  · Cross-channel link │   │                     │
│  · search_kb          │   │                       │   │  Mock: thread-safe  │
│  · get_customer_hist  │   │  knowledge_service    │   │  deque, zero config │
│  · create_ticket      │   │  · KB search          │   └─────────────────────┘
│  · escalate_to_human  │   │  · Confidence scoring │
│  · analyze_sentiment  │   │                       │   ┌─────────────────────┐
│  · update_ticket      │   │  metrics_service      │   │  Workers  workers/  │
└──────────────────────┘   │  · Event log          │   │  message_processor  │
                           │  · Time aggregation   │   │  metrics_collector  │
                           └───────────┬───────────┘   └─────────────────────┘
                                       ▼
                        ┌──────────────────────────────┐
                        │  Database Layer  database/    │
                        │                              │
                        │  PostgreSQL (production)     │
                        │  SQLite (dev/test fallback)  │
                        │                              │
                        │  8 tables:                   │
                        │  · customers                 │
                        │  · customer_identifiers      │
                        │  · conversations             │
                        │  · messages                  │
                        │  · tickets                   │
                        │  · knowledge_base            │
                        │  · channel_configs           │
                        │  · agent_metrics             │
                        │                              │
                        │  SQLAlchemy 2.0 ORM          │
                        │  migrations/001_initial.sql  │
                        └──────────────────────────────┘
```

---

## Component Details

### Channel Adapters (`channels/`)

Each adapter implements two functions and is self-contained:

| Adapter | `normalize()` input | `send_reply()` output |
|---------|--------------------|-----------------------|
| `email_channel.py` | `from_email`, `subject`, `body` | SMTP / Gmail API (simulated) |
| `whatsapp_channel.py` | Twilio form data or Meta Cloud API | Twilio WhatsApp API (simulated) |
| `web_form_channel.py` | `name`, `email`, `description`, `issue_type` | Inline JSON or email fallback |

All adapters produce a unified `MessagePayload` dict: `channel`, `raw_text`, `sender_email`, `sender_phone`, `sender_name`, `subject`, `thread_id`, `external_id`, `metadata`, `normalized_at`.

### AI Agent (`agent/`)

```
AgentInput
  → analyze_sentiment()       anger / frustration / urgency scoring
  → get_customer_history()    prior tickets, plan, account health
  → search_knowledge_base()   12 KB categories, confidence 0.0–1.0
  → create_ticket()           TKT-YYYYMMDD-XXXX reference
  → format_response(channel)  channel-specific formatting
  → escalate_to_human()       if escalation rules triggered
AgentOutput
  { response, ticket_ref, sentiment, kb_confidence, should_escalate, ... }
```

**Escalation triggers:**

| Trigger | Threshold | Destination queue |
|---------|-----------|-------------------|
| `anger_score` | > 0.7 | `senior-support` |
| `kb_confidence` | < 0.3 | `technical-support` |
| `"refund"` keyword | — | `billing-team` |
| `"lawyer"` / `"legal"` | — | `legal-team` |
| `"hacked"` / `"breach"` | — | `security-team` |
| `"cancel"` / churn risk | — | `csm-retention` |
| Enterprise + frustrated | — | `enterprise-csm` |
| VIP customer | Any | `enterprise-csm` priority |

### Cross-Channel Identity Resolution (`crm/customer_service.py`)

```
identify_customer(customer_ref, email, phone)

  Strategy 1: direct customer_ref match    →  exact customers table lookup
  Strategy 2: email address lookup         →  customer_identifiers table
  Strategy 3: phone number lookup (E.164)  →  customer_identifiers table
  Strategy 4: auto-create guest profile    →  new row + identifier + link to channel
```

On every request, the AI agent receives the customer's full history: all prior tickets, channels used, sentiment trend, account plan, and account health score.

### CRM Ticket State Machine (`crm/ticket_service.py`)

```
OPEN → IN_PROGRESS → WAITING_CUSTOMER → RESOLVED
                   → ESCALATED        → IN_PROGRESS → RESOLVED
     → ESCALATED (immediate: high anger, legal, security triggers)
```

**SLA Matrix — hours to first response:**

| Plan | Critical | High | Medium | Low |
|------|---------|------|--------|-----|
| Starter | 4h | 12h | 24h | 48h |
| Growth | 2h | 6h | 12h | 24h |
| Business | 1h | 2h | 4h | 8h |
| Enterprise | 30m | 1h | 2h | 4h |

---

## Data Flows

### Web Form Submission (Synchronous)

```
Browser
  → POST /support/submit
  → _process_message()
  → web_form_channel.normalize()
  → customer_service.identify_customer()
  → agent.run()  {KB search · sentiment · response generation}
  → ticket_service.create_ticket()
  → ticket_service.escalate_ticket()  [if triggered]
  → web_form_channel.send_reply()
  → metrics_service.record_event()
  → kafka_client.publish("fte.tickets.incoming")
  → APIResponse { success, data: { ticket_ref, response, sentiment, ... } }
```

### Email / WhatsApp Webhooks (Asynchronous)

```
Gmail / Twilio
  → POST /webhooks/gmail|whatsapp
  → HTTP 200 "accepted"  [returned immediately — webhook timeout avoided]
  → FastAPI BackgroundTask: _process_webhook_async()
     → [same 9-stage pipeline]
     → email_channel.send_reply() or whatsapp_channel.send_reply()
```

Twilio requires a response within 15 seconds. Gmail Pub/Sub requires response within 10 seconds. BackgroundTasks ensure the HTTP response is immediate.

### Kafka Event Flow

```
Stage 9 publish → fte.tickets.incoming     [every processed message]
              → fte.email.outbound        [email replies sent]
              → fte.whatsapp.outbound     [WhatsApp replies sent]
              → fte.escalations          [escalation events]
              → fte.metrics             [agent performance data]

Failure → fte.dead-letter               [for replay]

Workers consume → metrics_collector aggregates → GET /metrics/* endpoints
```

---

## Technology Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Web framework | FastAPI | Async, auto OpenAPI docs, Pydantic v2 type safety |
| AI SDK | OpenAI Agents SDK + rule-based fallback | Hackathon requirement; fallback ensures zero-credential demo |
| Database | PostgreSQL + SQLite fallback | Production-grade + zero-config dev/test |
| ORM | SQLAlchemy 2.0 | Industry standard; parameterized queries prevent SQL injection |
| Event bus | Kafka + in-memory mock | Decoupled architecture; mock enables local dev with no external services |
| Webhook handling | FastAPI BackgroundTasks | Returns HTTP 200 immediately; processing is non-blocking |
| Frontend | Next.js 14 App Router + TypeScript + Tailwind | Modern, fast, Vercel-native |
| Containerization | Docker multi-stage build | Small final image (~200MB); non-root security; deterministic builds |
| Orchestration | Kubernetes + HPA | CPU-based auto-scaling; production-proven |

---

## Security Design

| Control | Implementation |
|---------|---------------|
| Input validation | Pydantic v2 on all API request models |
| SQL injection | SQLAlchemy parameterized queries only |
| Webhook authentication | Twilio HMAC-SHA256 signature validation |
| Secret management | Environment variables only; `.env.example` documents all |
| CORS | Configured to specific frontend domains |
| Container | Non-root `appuser`; `PORT=7860` for HF Spaces |
| API keys | Server-side only; never passed to frontend |

---

## Scaling Design

| Component | Scaling Strategy |
|-----------|-----------------|
| API | Stateless; K8s HPA 2 → 10 replicas on CPU >70% |
| Workers | Kafka consumer groups; K8s HPA 2 → 6 replicas |
| Database | SQLAlchemy connection pool (pool_size=5, max_overflow=10) |
| Frontend | Vercel Edge Network — global CDN |
| Kafka | Partition-based parallelism; add partitions to scale workers linearly |

---

## Fallback Hierarchy

```
Dependency       Failure mode              Fallback
──────────────   ─────────────────────── ─────────────────────────────────
OpenAI API       Quota / network error    Rule-based KB matching + template
Kafka broker     Unreachable              Thread-safe in-memory mock broker
PostgreSQL       Connection failed        SQLite in-memory (sqlite://)
Channel send()   Gateway error            Ticket created; delivery_status=failed
```

The system continues processing and persisting tickets under any single-dependency failure.
