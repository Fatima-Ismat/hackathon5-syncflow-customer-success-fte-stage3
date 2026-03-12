# Stage 3 Implementation Plan
## SyncFlow Customer Success Digital FTE

**Owner:** Ismat Fatima | **Hackathon 5 Final Stage**

---

## Evolution: Stage 1 → Stage 2 → Stage 3

### Stage 1 (Complete)
- Standalone agent prototype (`src/agent/customer_success_agent.py`)
- MCP server with 5 tools (`src/agent/mcp_server.py`)
- Rule-based KB search and sentiment analysis
- CLI demo with test cases

### Stage 2 (Complete)
- FastAPI backend (`backend/main.py`) with 10 endpoints
- CRM service layer: ticket, customer, knowledge, metrics services
- Multi-channel adapters: email, WhatsApp, web form
- 9-stage message processing pipeline
- SQLAlchemy ORM models + PostgreSQL schema
- Next.js 14 frontend with 3 pages
- Stage 1 agent bridge integration

### Stage 3 (This Implementation)

Built on top of Stage 1+2. No existing code removed.

---

## Stage 3 Deliverables

| Phase | Deliverable | Status |
|-------|------------|--------|
| A | Audit + plan (this document) | ✅ |
| B | OpenAI Agents SDK production agent (`agent/`) | ✅ |
| C | PostgreSQL CRM upgrades (`database/`) | ✅ |
| D | Channel handler upgrades (`channels/`) | ✅ |
| E | Kafka event streaming (`kafka_client.py`, `workers/`) | ✅ |
| F | Final FastAPI API layer (`api/main.py`) | ✅ |
| G | Professional frontend upgrades | ✅ |
| H | E2E + load tests (`tests/`) | ✅ |
| I | K8s deployment manifests (`k8s/`) | ✅ |
| J | HF Spaces + Vercel deployment | ✅ |
| K | Documentation + runbook (`docs/`) | ✅ |
| L | Professional cleanup | ✅ |

---

## Key Architectural Decisions

### 1. Agent SDK Strategy
- **Primary**: OpenAI Agents SDK (`agents` package) when available
- **Fallback**: Rule-based orchestration in `agent/customer_success_agent.py`
- This ensures the demo works without an OpenAI API key

### 2. Database Strategy
- **Production**: PostgreSQL (Neon/Supabase free tier)
- **Development**: SQLite (auto-detected via `DATABASE_URL` env var)
- **Testing**: SQLite in-memory (`DATABASE_URL=sqlite://`)

### 3. Kafka Strategy
- **Production**: Confluent Cloud or self-hosted
- **Development/Demo**: In-memory mock broker (thread-safe deque)
- `KAFKA_MOCK_MODE=true` → mock; `false` + bootstrap servers → real

### 4. Channel Strategy
- All three channels implemented with mock fallback
- Real credentials optional — system works without Gmail API/Twilio
- Webhook endpoints work for live demos

---

## File Structure (Stage 3 Final)

```
Hackathon5-Customer-Success-FTE-Stage3/
├── agent/                          ← NEW: OpenAI Agents SDK production agent
│   ├── __init__.py
│   ├── customer_success_agent.py
│   ├── tools.py                    ← @function_tool compatible tools
│   ├── prompts.py                  ← System prompts
│   ├── formatters.py               ← Channel-aware formatters
│   └── models.py                   ← Pydantic models
├── api/                            ← NEW: Final production API
│   ├── __init__.py
│   └── main.py                     ← 15+ endpoints, webhooks, CORS
├── backend/                        ← PRESERVED: Stage 2 API (backward compat)
│   ├── main.py
│   └── agent_bridge.py
├── channels/                       ← PRESERVED + upgraded
│   ├── email_channel.py
│   ├── whatsapp_channel.py
│   └── web_form_channel.py
├── crm/                            ← PRESERVED: Stage 2 CRM services
│   ├── ticket_service.py
│   ├── customer_service.py
│   ├── knowledge_service.py
│   └── metrics_service.py
├── database/                       ← UPGRADED: DB connection + queries
│   ├── models.py
│   ├── schema.sql
│   ├── connection.py               ← NEW: SQLAlchemy engine + session
│   ├── queries.py                  ← NEW: Business logic queries
│   ├── seed.py                     ← NEW: Demo data seeder
│   └── migrations/
│       └── 001_initial.sql         ← NEW: Production schema migration
├── workers/                        ← UPGRADED: Kafka-aware workers
│   ├── message_worker.py           ← PRESERVED: Stage 2 pipeline
│   ├── message_processor.py        ← NEW: Kafka consumer worker
│   └── metrics_collector.py        ← NEW: Metrics Kafka consumer
├── frontend/                       ← UPGRADED: Polished Next.js
│   ├── app/
│   │   ├── page.tsx
│   │   ├── support/page.tsx
│   │   ├── ticket-status/page.tsx
│   │   └── admin/page.tsx
│   ├── components/
│   │   ├── SupportForm.tsx
│   │   ├── TicketCard.tsx
│   │   └── MetricsCard.tsx
│   └── lib/api.ts
├── tests/                          ← UPGRADED: Full pytest suite
│   ├── conftest.py                 ← NEW
│   ├── test_agent.py               ← NEW
│   ├── test_channels.py            ← NEW
│   ├── test_api.py                 ← NEW
│   ├── test_multichannel_e2e.py    ← NEW
│   └── load_test.py                ← NEW: Locust load tests
├── k8s/                            ← NEW: K8s manifests
│   ├── namespace.yaml
│   ├── configmap.yaml
│   ├── secrets.yaml
│   ├── deployment-api.yaml
│   ├── deployment-worker.yaml
│   ├── service.yaml
│   ├── ingress.yaml
│   └── hpa.yaml
├── docs/                           ← NEW: Full documentation
│   ├── deployment.md
│   ├── operations-runbook.md
│   ├── architecture.md
│   └── testing.md
├── src/                            ← PRESERVED: Stage 1 prototype
│   └── agent/
│       ├── customer_success_agent.py
│       └── mcp_server.py
├── context/                        ← PRESERVED: Domain knowledge
├── specs/                          ← UPGRADED
│   ├── stage3-plan.md              ← NEW (this file)
│   ├── transition-checklist.md     ← NEW
│   └── [existing Stage 2 specs]
├── Dockerfile                      ← NEW: Multi-stage production build
├── docker-compose.yml              ← NEW: Full local stack
├── kafka_client.py                 ← NEW: Kafka + mock broker
├── requirements.txt                ← UPGRADED: All dependencies
├── .env.example                    ← NEW: Configuration template
└── README.md                       ← UPGRADED: Judge-ready final README
```
