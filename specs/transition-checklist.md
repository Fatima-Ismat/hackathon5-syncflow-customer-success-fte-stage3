# Stage 3 Transition Checklist
## SyncFlow Customer Success Digital FTE

**Owner:** Ismat Fatima

---

## Pre-Submission Checklist

### Code Quality
- [x] All Python files have docstrings
- [x] Type hints throughout
- [x] No broken imports
- [x] No hardcoded secrets in code
- [x] No debug print statements in production code
- [x] Structured logging in all modules
- [x] Consistent error handling

### Functionality
- [x] Web form submission end-to-end works
- [x] Email webhook accepted and processed
- [x] WhatsApp webhook accepted and processed
- [x] Ticket creation with SLA deadline
- [x] Escalation routing to correct queue
- [x] Customer identity resolution (known + guest)
- [x] AI agent response generation
- [x] Sentiment analysis
- [x] Confidence scoring
- [x] Channel-aware response formatting
- [x] Cross-channel customer continuity

### API
- [x] `GET /health` — liveness probe
- [x] `GET /readiness` — readiness probe
- [x] `POST /support/submit` — primary intake
- [x] `GET /support/ticket/{id}` — status lookup
- [x] `GET /tickets` — list with filters
- [x] `GET /tickets/{ref}` — get single ticket
- [x] `POST /tickets/{ref}/reply` — human reply
- [x] `POST /tickets/{ref}/escalate` — manual escalation
- [x] `POST /tickets/{ref}/resolve` — resolve ticket
- [x] `GET /conversations/{id}` — conversation thread
- [x] `GET /customers/{ref}` — customer profile
- [x] `POST /customers/lookup` — cross-channel lookup
- [x] `POST /webhooks/gmail` — Gmail inbound
- [x] `POST /webhooks/whatsapp` — WhatsApp inbound
- [x] `POST /webhooks/whatsapp/status` — delivery status
- [x] `GET /metrics/summary` — agent metrics
- [x] `GET /metrics/channels` — channel breakdown
- [x] `GET /metrics/sentiment` — sentiment distribution
- [x] Swagger docs at `/docs`

### Database
- [x] PostgreSQL schema defined
- [x] SQLite fallback for dev/test
- [x] Migration file (001_initial.sql)
- [x] Seed data (7 customers + 12 KB articles)
- [x] SQLAlchemy ORM models (8 tables)
- [x] Connection management
- [x] Query helpers

### Kafka
- [x] All 8 topics defined
- [x] Producer with confluent-kafka / kafka-python support
- [x] In-memory mock broker fallback
- [x] Kafka consumer worker
- [x] Metrics collector worker
- [x] Dead-letter queue handling

### Testing
- [x] `pytest tests/test_agent.py` passes
- [x] `pytest tests/test_channels.py` passes
- [x] `pytest tests/test_api.py` passes
- [x] `pytest tests/test_multichannel_e2e.py` passes
- [x] Load test file syntax valid
- [x] Test fixtures in conftest.py

### Deployment
- [x] Dockerfile (multi-stage, non-root user)
- [x] docker-compose.yml (full stack)
- [x] K8s namespace.yaml
- [x] K8s configmap.yaml
- [x] K8s secrets.yaml (template)
- [x] K8s deployment-api.yaml
- [x] K8s deployment-worker.yaml
- [x] K8s service.yaml
- [x] K8s ingress.yaml
- [x] K8s hpa.yaml
- [x] HF Spaces instructions in docs/deployment.md
- [x] Vercel instructions in docs/deployment.md
- [x] .env.example

### Frontend
- [x] Support form (name, email, subject, category, priority, message)
- [x] Form validation
- [x] Loading state
- [x] Success state with ticket ID
- [x] Error state
- [x] Ticket status lookup page
- [x] Admin metrics dashboard
- [x] Professional styling (Tailwind)
- [x] Responsive layout
- [x] NEXT_PUBLIC_API_URL env var

### Documentation
- [x] README.md (judge-ready, comprehensive)
- [x] docs/deployment.md
- [x] docs/operations-runbook.md
- [x] docs/architecture.md
- [x] docs/testing.md
- [x] specs/stage3-plan.md
- [x] specs/transition-checklist.md (this file)

---

## Manual Steps Required (For You)

### To Deploy Backend to Hugging Face:
1. Create account at huggingface.co
2. Create new Space (Docker SDK)
3. Add secrets: `OPENAI_API_KEY`, `DATABASE_URL`
4. Push code to Space repo

### To Deploy Frontend to Vercel:
1. Create account at vercel.com
2. Import frontend folder (or push to GitHub first)
3. Set `NEXT_PUBLIC_API_URL` to your HF Space URL
4. Deploy

### To Enable Live Channels:
- **WhatsApp**: Create Twilio account, get WhatsApp sandbox, set TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN
- **Gmail**: Enable Gmail API, download credentials.json, set GMAIL_CREDENTIALS_JSON

### For PostgreSQL:
1. Create free database at neon.tech or supabase.com
2. Run: `psql "$DATABASE_URL" -f database/migrations/001_initial.sql`
3. Run: `DATABASE_URL="..." python database/seed.py`

---

## Known Limitations (Documented)

| Limitation | Impact | Workaround |
|-----------|--------|------------|
| No Gmail API live credentials | Email replies not sent | Mock mode — responses in API response body |
| No Twilio live credentials | WhatsApp replies not sent | Mock mode — responses logged |
| OpenAI API optional | Agent uses rule-based fallback | Fallback produces valid responses |
| Kafka optional | Uses in-memory mock broker | All events stored in memory (lost on restart) |
| Free HF Space sleeps | First request ~30s cold start | Upgrade tier or use keep-alive ping |
