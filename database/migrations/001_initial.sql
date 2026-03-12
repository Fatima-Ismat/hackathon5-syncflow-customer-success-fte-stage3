-- ============================================================
-- Migration 001: Initial Schema
-- SyncFlow Customer Success Digital FTE — Stage 3
-- ============================================================
-- Run: psql -U postgres -d syncflow_crm -f database/migrations/001_initial.sql

BEGIN;

-- ── Extensions ───────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- Uncomment for vector search (requires pgvector):
-- CREATE EXTENSION IF NOT EXISTS vector;

-- ── Customers ────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customers (
    id              SERIAL PRIMARY KEY,
    customer_ref    VARCHAR(20)  UNIQUE NOT NULL,
    name            VARCHAR(200) NOT NULL,
    company         VARCHAR(200),
    plan            VARCHAR(20)  NOT NULL DEFAULT 'starter'
                        CHECK (plan IN ('starter','growth','business','enterprise')),
    is_vip          BOOLEAN NOT NULL DEFAULT FALSE,
    account_health  VARCHAR(20)  NOT NULL DEFAULT 'healthy'
                        CHECK (account_health IN ('healthy','at_risk','churned')),
    mrr             NUMERIC(10,2) NOT NULL DEFAULT 0.00,
    csat_avg        NUMERIC(3,2),
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Customer Identifiers ──────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS customer_identifiers (
    id               SERIAL PRIMARY KEY,
    customer_id      INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    identifier_type  VARCHAR(30) NOT NULL
                         CHECK (identifier_type IN ('email','phone','whatsapp','external_id','oauth')),
    identifier_value VARCHAR(500) NOT NULL,
    channel          VARCHAR(30),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (identifier_type, identifier_value)
);

-- ── Conversations ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    channel         VARCHAR(20) NOT NULL,
    channel_thread_id VARCHAR(500),
    subject         VARCHAR(500),
    status          VARCHAR(30) NOT NULL DEFAULT 'active',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Messages ──────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS messages (
    id                  SERIAL PRIMARY KEY,
    ticket_id           INTEGER REFERENCES tickets(id) ON DELETE SET NULL,
    conversation_id     INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
    direction           VARCHAR(10) NOT NULL CHECK (direction IN ('inbound','outbound')),
    channel             VARCHAR(20) NOT NULL,
    content             TEXT NOT NULL,
    sender_ref          VARCHAR(200),
    channel_message_id  VARCHAR(500),
    delivery_status     VARCHAR(30) DEFAULT 'sent',
    sentiment_score     NUMERIC(4,3),
    confidence_score    NUMERIC(4,3),
    tools_used          TEXT[],
    processing_ms       INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Tickets ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tickets (
    id                  SERIAL PRIMARY KEY,
    ticket_ref          VARCHAR(20) UNIQUE NOT NULL,
    customer_id         INTEGER REFERENCES customers(id) ON DELETE SET NULL,
    conversation_id     INTEGER REFERENCES conversations(id) ON DELETE SET NULL,
    subject             VARCHAR(500),
    channel             VARCHAR(20) NOT NULL DEFAULT 'web_form',
    status              VARCHAR(30) NOT NULL DEFAULT 'open'
                            CHECK (status IN ('open','in_progress','waiting_customer','escalated','resolved')),
    priority            VARCHAR(20) NOT NULL DEFAULT 'medium'
                            CHECK (priority IN ('critical','high','medium','low')),
    sentiment_score     NUMERIC(4,3),
    kb_confidence       NUMERIC(4,3),
    kb_section          VARCHAR(100),
    ai_response         TEXT,
    escalated           BOOLEAN NOT NULL DEFAULT FALSE,
    escalation_reason   VARCHAR(100),
    escalation_queue    VARCHAR(100),
    escalation_id       VARCHAR(50),
    resolution_notes    TEXT,
    sla_deadline        TIMESTAMPTZ,
    resolved_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Knowledge Base ────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS knowledge_base (
    id          SERIAL PRIMARY KEY,
    section     VARCHAR(100) NOT NULL,
    title       VARCHAR(300) NOT NULL,
    content     TEXT NOT NULL,
    tags        TEXT,
    usage_count INTEGER NOT NULL DEFAULT 0,
    -- Uncomment for pgvector semantic search:
    -- embedding  vector(1536),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Channel Configs ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS channel_configs (
    id          SERIAL PRIMARY KEY,
    channel     VARCHAR(20) UNIQUE NOT NULL,
    enabled     BOOLEAN NOT NULL DEFAULT TRUE,
    config      JSONB,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Agent Metrics ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS agent_metrics (
    id                  SERIAL PRIMARY KEY,
    event_type          VARCHAR(50) NOT NULL,
    channel             VARCHAR(20),
    ticket_ref          VARCHAR(20),
    customer_ref        VARCHAR(20),
    sentiment           VARCHAR(30),
    confidence          NUMERIC(4,3),
    escalated           BOOLEAN DEFAULT FALSE,
    escalation_reason   VARCHAR(100),
    processing_ms       INTEGER,
    metadata            JSONB,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ── Indexes ───────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_customers_ref         ON customers(customer_ref);
CREATE INDEX IF NOT EXISTS idx_customers_health      ON customers(account_health);
CREATE INDEX IF NOT EXISTS idx_identifiers_type_val  ON customer_identifiers(identifier_type, identifier_value);
CREATE INDEX IF NOT EXISTS idx_identifiers_customer  ON customer_identifiers(customer_id);
CREATE INDEX IF NOT EXISTS idx_tickets_ref           ON tickets(ticket_ref);
CREATE INDEX IF NOT EXISTS idx_tickets_customer      ON tickets(customer_id);
CREATE INDEX IF NOT EXISTS idx_tickets_status        ON tickets(status);
CREATE INDEX IF NOT EXISTS idx_tickets_priority      ON tickets(priority);
CREATE INDEX IF NOT EXISTS idx_tickets_channel       ON tickets(channel);
CREATE INDEX IF NOT EXISTS idx_tickets_created       ON tickets(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_ticket       ON messages(ticket_id);
CREATE INDEX IF NOT EXISTS idx_messages_created      ON messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_metrics_event         ON agent_metrics(event_type);
CREATE INDEX IF NOT EXISTS idx_metrics_created       ON agent_metrics(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_kb_section            ON knowledge_base(section);
CREATE INDEX IF NOT EXISTS idx_kb_tags               ON knowledge_base USING GIN (to_tsvector('english', COALESCE(tags,'')));

-- ── Auto-update updated_at ────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
    CREATE TRIGGER trg_customers_updated
        BEFORE UPDATE ON customers
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TRIGGER trg_tickets_updated
        BEFORE UPDATE ON tickets
        FOR EACH ROW EXECUTE FUNCTION update_updated_at();
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- ── Default Channel Configs ───────────────────────────────────────────────────
INSERT INTO channel_configs (channel, enabled, config) VALUES
    ('web_form',  TRUE, '{"max_message_length": 5000}'),
    ('email',     TRUE, '{"mock_mode": true, "provider": "gmail"}'),
    ('whatsapp',  TRUE, '{"mock_mode": true, "provider": "twilio"}')
ON CONFLICT (channel) DO NOTHING;

COMMIT;
