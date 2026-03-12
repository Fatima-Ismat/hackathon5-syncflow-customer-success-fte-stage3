# Deployment Guide
## SyncFlow Customer Success Digital FTE — Stage 3

**Owner:** Ismat Fatima | **Hackathon 5 — Final Stage**

---

## Deployment Overview

| Target | Technology | URL Pattern |
|--------|-----------|-------------|
| Backend API | Hugging Face Spaces (Docker SDK) | `https://YOUR-USERNAME-syncflow-api.hf.space` |
| Frontend | Vercel (Next.js) | `https://syncflow-support.vercel.app` |
| Database | PostgreSQL via Neon / Supabase / Railway | connection string |
| Kafka | Confluent Cloud (optional) | bootstrap servers |

**Zero-credential demo:** All external services (OpenAI, Kafka, Gmail, Twilio) have mock fallbacks. The API runs fully with `KAFKA_MOCK_MODE=true` and SQLite.

---

## Quick Deploy (5 minutes)

```bash
# Step 1: Start API locally (SQLite + mock Kafka — no credentials needed)
pip install -r requirements.txt
uvicorn api.main:app --port 8000
# Swagger UI: http://localhost:8000/docs

# Step 2: Test
curl http://localhost:8000/health
curl -X POST http://localhost:8000/support/submit \
  -H "Content-Type: application/json" \
  -d '{"channel":"web_form","customer_ref":"C-1042","message":"Hello, test deploy"}'

# Step 3: Run tests
pytest -q
```

---

## 1. Backend — Hugging Face Spaces

### Prerequisites

- Hugging Face account: https://huggingface.co
- (Optional) `OPENAI_API_KEY` from OpenAI
- (Optional) PostgreSQL connection string (Neon free tier recommended)

### Step 1: Create a Docker Space

1. Go to https://huggingface.co/spaces
2. Click **New Space**
3. Settings:
   - **Space name:** `syncflow-api`
   - **SDK:** Docker
   - **Visibility:** Public (for demo)

### Step 2: Configure Secrets

In your Space → Settings → Repository secrets:

```
OPENAI_API_KEY        sk-...                           (optional)
DATABASE_URL          postgresql://user:pass@host/db   (optional — SQLite used without)
KAFKA_MOCK_MODE       true
PORT                  7860
CORS_ORIGINS          https://syncflow-support.vercel.app,http://localhost:3000
```

Optional — for live channel integrations:
```
TWILIO_ACCOUNT_SID    AC...
TWILIO_AUTH_TOKEN     ...
GMAIL_CREDENTIALS_JSON  {...}
WHATSAPP_VERIFY_TOKEN   syncflow_verify_2025
```

### Step 3: Push Code

```bash
# Clone your Space repository
git clone https://huggingface.co/spaces/YOUR-USERNAME/syncflow-api
cd syncflow-api

# Copy project files
cp -r /path/to/Hackathon5-Customer-Success-FTE-Stage3/* .

# Push — Space auto-builds and deploys using Dockerfile
git add .
git commit -m "Deploy SyncFlow Customer Success FTE — Stage 3"
git push
```

### Step 4: Verify Deployment

```bash
# Health check
curl https://YOUR-USERNAME-syncflow-api.hf.space/health
# Expected: {"status":"ok","version":"3.0.0",...}

# Test ticket submission
curl -X POST https://YOUR-USERNAME-syncflow-api.hf.space/support/submit \
  -H "Content-Type: application/json" \
  -d '{
    "channel": "web_form",
    "customer_ref": "C-1042",
    "message": "Testing production deployment"
  }'

# Open Swagger UI
# https://YOUR-USERNAME-syncflow-api.hf.space/docs
```

### Hugging Face Notes

- The `Dockerfile` sets `PORT=7860` by default (required for HF Spaces)
- Free tier: Space sleeps after 48h of inactivity — first request may take ~30s cold start
- Use HF "Keep alive" API or upgrade to paid tier for 24/7 uptime
- All logs visible in: Space → Logs tab

---

## 2. Frontend — Vercel

### Prerequisites

- Vercel account: https://vercel.com
- Backend URL from Hugging Face (e.g. `https://YOUR-USERNAME-syncflow-api.hf.space`)

### Option A: Vercel Dashboard (Recommended)

1. Push your project to GitHub (the full repo — Vercel will use `frontend/` as root)
2. Go to https://vercel.com/new → **Import from GitHub** → select your repo
3. In **Configure Project**:
   - **Framework Preset:** Next.js (auto-detected)
   - **Root Directory:** `frontend`
   - **Build Command:** `npm run build` (default)
   - **Output Directory:** `.next` (default)
4. Expand **Environment Variables** and add:
   ```
   Name:  NEXT_PUBLIC_API_URL
   Value: https://YOUR-USERNAME-syncflow-api.hf.space
   ```
5. Click **Deploy**
6. Once deployed, note your Vercel URL (e.g. `https://syncflow-support.vercel.app`)
7. Go back to your HF Space secrets and set:
   ```
   CORS_ORIGINS = https://syncflow-support.vercel.app,http://localhost:3000
   ```

### Option B: Vercel CLI

```bash
cd frontend
npm install -g vercel
vercel login
vercel --prod
# When prompted:
#   Root directory?     ./  (already in frontend/)
#   Framework?          Next.js
#   Set env variable:   NEXT_PUBLIC_API_URL = https://YOUR-USERNAME-syncflow-api.hf.space
```

### Verify Frontend

```bash
# 1. Open your Vercel URL → Home page should load
# 2. Navigate to /support → submit a test request
# 3. Copy the returned ticket reference (TKT-YYYYMMDD-XXXX)
# 4. Navigate to /ticket-status → paste reference → should show ticket details
# 5. Navigate to /admin → API status should show "Online", metrics should load
```

### Vercel Configuration (`frontend/vercel.json`)

```json
{
  "framework": "nextjs",
  "buildCommand": "npm run build",
  "outputDirectory": ".next",
  "devCommand": "npm run dev",
  "installCommand": "npm install"
}
```

> **Note:** `NEXT_PUBLIC_API_URL` must be set in the Vercel Dashboard (not in `vercel.json`)
> because it is a build-time variable that must be injected at build time, not at runtime.
> The `.env.example` in `frontend/` documents the required variables.

### Frontend Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | Yes | Backend API base URL. Set in Vercel Dashboard. |

Local development: copy `frontend/.env.example` → `frontend/.env.local` and set the URL to `http://localhost:8000`.

---

## 3. Database — Neon PostgreSQL (Free Tier)

### Step 1: Create Database

1. Go to https://neon.tech
2. New project → name it `syncflow-crm`
3. Copy the connection string: `postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/syncflow_crm?sslmode=require`

### Step 2: Run Migration

```bash
# Run the DDL (creates all 8 tables, indexes, triggers)
psql "postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/syncflow_crm?sslmode=require" \
  -f database/migrations/001_initial.sql
```

### Step 3: Seed Demo Data

```bash
DATABASE_URL="postgresql://user:pass@..." python database/seed.py
# Seeds: 7 customers (C-1042 through C-8901) + 12 KB articles
```

### Step 4: Add to HF Secrets

```
DATABASE_URL = postgresql://user:pass@ep-xxx.us-east-1.aws.neon.tech/syncflow_crm?sslmode=require
```

### Alternative: Supabase

1. https://supabase.com → New project
2. Settings → Database → Connection String (URI format)
3. Run migration via Supabase SQL Editor (paste contents of `001_initial.sql`)
4. Run seed: `DATABASE_URL="postgresql://..." python database/seed.py`

---

## 4. Kafka — Confluent Cloud (Optional)

The API works fully without real Kafka (`KAFKA_MOCK_MODE=true` by default). For production event streaming:

### Step 1: Create Cluster

1. Go to https://confluent.cloud
2. Create a free Serverless cluster
3. Create API Key under your cluster

### Step 2: Create Topics

```
fte.tickets.incoming
fte.email.inbound
fte.email.outbound
fte.whatsapp.inbound
fte.whatsapp.outbound
fte.metrics
fte.escalations
fte.dead-letter
```

### Step 3: Configure Environment

```bash
KAFKA_BOOTSTRAP_SERVERS = pkc-xxx.us-east-1.aws.confluent.cloud:9092
KAFKA_SECURITY_PROTOCOL = SASL_SSL
KAFKA_SASL_MECHANISM    = PLAIN
KAFKA_SASL_USERNAME     = YOUR_CONFLUENT_API_KEY
KAFKA_SASL_PASSWORD     = YOUR_CONFLUENT_API_SECRET
KAFKA_MOCK_MODE         = false
```

---

## 5. Local Development

### Backend (Zero Config)

```bash
# Clone
git clone https://github.com/ismatfatima/syncflow-customer-success
cd Hackathon5-Customer-Success-FTE-Stage3

# Install
python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt

# Optional: copy and edit env
cp .env.example .env

# Seed demo data (optional — API works without)
python database/seed.py

# Start API (SQLite + mock Kafka — zero credentials)
uvicorn api.main:app --reload --port 8000
# → http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
npm run dev
# → http://localhost:3000
```

### Docker Compose (Full Stack)

```bash
# Start PostgreSQL + Kafka + Zookeeper
docker-compose up -d postgres kafka zookeeper

# Wait ~10s for services, then start API
docker-compose up api

# Full stack (API + worker + frontend)
docker-compose up

# View logs
docker-compose logs -f api
```

### Run Tests

```bash
# Fast core tests (94 tests, ~21s, zero warnings)
pytest -q

# Full suite including slow burst tests
pytest -m "not load" -v

# Load test (requires live server)
pip install locust
locust -f tests/load_test.py --host=http://localhost:8000 \
  --users=10 --spawn-rate=2 --run-time=30s --headless
```

---

## 6. Kubernetes Deployment

```bash
# Apply all manifests
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secrets.yaml      # fill in real values first
kubectl apply -f k8s/deployment-api.yaml
kubectl apply -f k8s/deployment-worker.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
kubectl apply -f k8s/hpa.yaml

# Verify
kubectl get pods -n syncflow
kubectl get hpa -n syncflow

# Check API health
kubectl port-forward svc/syncflow-api 8000:8000 -n syncflow
curl http://localhost:8000/health
```

**HPA Configuration:**
- API: 2 → 10 replicas, CPU threshold 70%
- Worker: 2 → 6 replicas, CPU threshold 70%

---

## 7. Environment Variables Reference

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `OPENAI_API_KEY` | No | — | OpenAI Agents SDK; rule-based fallback if absent |
| `DATABASE_URL` | No | `sqlite:///./syncflow_dev.db` | PostgreSQL or SQLite |
| `KAFKA_MOCK_MODE` | No | `true` | `false` for real Confluent/Kafka |
| `KAFKA_BOOTSTRAP_SERVERS` | If Kafka | — | Kafka broker address |
| `KAFKA_SECURITY_PROTOCOL` | If Confluent | — | `SASL_SSL` |
| `KAFKA_SASL_USERNAME` | If Confluent | — | API key |
| `KAFKA_SASL_PASSWORD` | If Confluent | — | API secret |
| `TWILIO_ACCOUNT_SID` | No | — | Live WhatsApp; mock works without |
| `TWILIO_AUTH_TOKEN` | No | — | Twilio signature validation |
| `GMAIL_CREDENTIALS_JSON` | No | — | Gmail API OAuth credentials |
| `CORS_ORIGINS` | No | `localhost:3000` | Comma-separated allowed origins |
| `PORT` | No | `8000` | Server port (HF Spaces: `7860`) |
| `WEBHOOK_BASE_URL` | No | — | Full API URL for signature validation |
| `WHATSAPP_VERIFY_TOKEN` | No | `syncflow_verify_2025` | Meta webhook verification |

Full example: [.env.example](../.env.example)

---

## 8. Webhook Configuration (Production)

### Gmail Webhook

```bash
# Create Pub/Sub topic and subscription
gcloud pubsub topics create syncflow-gmail-push
gcloud pubsub subscriptions create syncflow-gmail-sub \
  --topic syncflow-gmail-push \
  --push-endpoint https://YOUR-API.hf.space/webhooks/gmail \
  --ack-deadline 20
```

### WhatsApp Webhook (Twilio)

1. Twilio Console → Messaging → WhatsApp Sandbox (or sender number)
2. **Webhook URL:** `https://YOUR-API.hf.space/webhooks/whatsapp`
3. **HTTP Method:** POST
4. **Status callback:** `https://YOUR-API.hf.space/webhooks/whatsapp/status`

---

## 9. Post-Deployment Verification Checklist

After any deployment:

- [ ] `GET /health` returns `{"status":"ok"}`
- [ ] `GET /readiness` returns HTTP 200
- [ ] `POST /support/submit` (web_form) returns ticket ref
- [ ] `GET /tickets` returns list
- [ ] `GET /metrics/summary` returns metrics object
- [ ] `GET /docs` shows Swagger UI with all 19 endpoints
- [ ] Frontend form submits successfully
- [ ] Ticket status page loads and shows correct data
- [ ] Admin dashboard shows metrics charts
- [ ] Gmail webhook test: `curl -X POST .../webhooks/gmail -d '{"from_email":"test@test.com","body":"Test"}'`
- [ ] WhatsApp webhook test: `curl -X POST .../webhooks/whatsapp -d "From=whatsapp:+14155550101&Body=Test"`
