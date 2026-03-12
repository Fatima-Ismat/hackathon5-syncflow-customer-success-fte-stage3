-- =============================================================================
-- CRM Database Schema – Stage 2
-- NovaSync Technologies / SyncFlow Customer Success Digital FTE
--
-- PostgreSQL 15+ compatible schema.
-- Run with: psql -U postgres -d syncflow_crm -f schema.sql
-- =============================================================================

-- Enable UUID extension (optional — used for external integrations)
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- =============================================================================
-- ENUMERATIONS
-- =============================================================================

DO $$ BEGIN
    CREATE TYPE ticket_status AS ENUM (
        'open', 'in_progress', 'waiting_customer', 'escalated', 'resolved'
    );
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE ticket_priority AS ENUM ('critical', 'high', 'medium', 'low');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE channel_type AS ENUM ('email', 'whatsapp', 'web_form');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE customer_plan AS ENUM ('starter', 'growth', 'business', 'enterprise');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN
    CREATE TYPE message_direction AS ENUM ('inbound', 'outbound');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;


-- =============================================================================
-- TABLE: customers
-- =============================================================================

CREATE TABLE IF NOT EXISTS customers (
    id               SERIAL PRIMARY KEY,
    customer_ref     VARCHAR(20)    NOT NULL UNIQUE,    -- C-1042
    name             VARCHAR(255)   NOT NULL,
    plan             customer_plan  NOT NULL DEFAULT 'starter',
    is_vip           BOOLEAN        NOT NULL DEFAULT FALSE,
    account_health   VARCHAR(50)    NOT NULL DEFAULT 'healthy', -- healthy | at_risk | churned
    mrr              NUMERIC(10,2),                              -- Monthly recurring revenue USD
    csat_average     NUMERIC(3,2),                              -- 1.00–5.00
    total_tickets    INT            NOT NULL DEFAULT 0,
    open_tickets     INT            NOT NULL DEFAULT 0,
    last_contact     TIMESTAMP WITH TIME ZONE,
    account_created  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_customers_customer_ref ON customers(customer_ref);
CREATE INDEX IF NOT EXISTS ix_customers_plan        ON customers(plan);
CREATE INDEX IF NOT EXISTS ix_customers_is_vip      ON customers(is_vip);

-- Auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS set_customers_updated_at ON customers;
CREATE TRIGGER set_customers_updated_at
    BEFORE UPDATE ON customers
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();


-- =============================================================================
-- TABLE: customer_identifiers
-- =============================================================================

CREATE TABLE IF NOT EXISTS customer_identifiers (
    id               SERIAL PRIMARY KEY,
    customer_id      INT            NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    identifier_type  VARCHAR(50)    NOT NULL,  -- email | phone | whatsapp | salesforce_id | hubspot_id
    identifier_value VARCHAR(255)   NOT NULL,
    is_primary       BOOLEAN        NOT NULL DEFAULT FALSE,
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_identifier UNIQUE (identifier_type, identifier_value)
);

CREATE INDEX IF NOT EXISTS ix_customer_identifiers_customer_id ON customer_identifiers(customer_id);
CREATE INDEX IF NOT EXISTS ix_customer_identifiers_value       ON customer_identifiers(identifier_value);


-- =============================================================================
-- TABLE: tickets
-- =============================================================================

CREATE TABLE IF NOT EXISTS tickets (
    id                 SERIAL PRIMARY KEY,
    ticket_ref         VARCHAR(30)      NOT NULL UNIQUE,  -- TKT-20260311-1234
    customer_id        INT              NOT NULL REFERENCES customers(id),
    channel            channel_type     NOT NULL,
    status             ticket_status    NOT NULL DEFAULT 'open',
    priority           ticket_priority  NOT NULL DEFAULT 'medium',

    subject            VARCHAR(500),
    topic              VARCHAR(100),    -- classified topic slug
    tags               JSONB,           -- ["billing", "vip"]
    assigned_to        VARCHAR(100)     NOT NULL DEFAULT 'ai_agent',

    -- Escalation
    escalation_reason  VARCHAR(100),
    escalation_queue   VARCHAR(100),
    escalation_id      VARCHAR(50),
    escalated_at       TIMESTAMP WITH TIME ZONE,

    -- SLA
    sla_deadline       TIMESTAMP WITH TIME ZONE,
    sla_breached       BOOLEAN          NOT NULL DEFAULT FALSE,
    resolution_time_s  INT,             -- seconds from create to resolve

    -- Agent quality
    agent_confidence   NUMERIC(4,3),    -- 0.000–1.000
    sentiment_at_open  VARCHAR(30),
    kb_used            BOOLEAN          NOT NULL DEFAULT FALSE,

    created_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    resolved_at        TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_tickets_customer_id ON tickets(customer_id);
CREATE INDEX IF NOT EXISTS ix_tickets_status      ON tickets(status);
CREATE INDEX IF NOT EXISTS ix_tickets_priority    ON tickets(priority);
CREATE INDEX IF NOT EXISTS ix_tickets_created_at  ON tickets(created_at DESC);
CREATE INDEX IF NOT EXISTS ix_tickets_sla         ON tickets(sla_deadline) WHERE sla_breached = FALSE;
CREATE INDEX IF NOT EXISTS ix_tickets_tags        ON tickets USING GIN(tags);

DROP TRIGGER IF EXISTS set_tickets_updated_at ON tickets;
CREATE TRIGGER set_tickets_updated_at
    BEFORE UPDATE ON tickets
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();


-- =============================================================================
-- TABLE: conversations
-- =============================================================================

CREATE TABLE IF NOT EXISTS conversations (
    id               SERIAL PRIMARY KEY,
    conversation_ref VARCHAR(30)   NOT NULL UNIQUE,  -- CONV-20260311-1234
    customer_id      INT           NOT NULL REFERENCES customers(id),
    channel          channel_type  NOT NULL,
    ticket_id        INT           REFERENCES tickets(id),
    status           VARCHAR(30)   NOT NULL DEFAULT 'active',  -- active | closed | archived
    turn_count       INT           NOT NULL DEFAULT 0,
    context_data     JSONB,        -- session token, form field data, etc.
    started_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    last_message_at  TIMESTAMP WITH TIME ZONE,
    closed_at        TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_conversations_customer_id ON conversations(customer_id);
CREATE INDEX IF NOT EXISTS ix_conversations_ticket_id   ON conversations(ticket_id);
CREATE INDEX IF NOT EXISTS ix_conversations_started_at  ON conversations(started_at DESC);


-- =============================================================================
-- TABLE: messages
-- =============================================================================

CREATE TABLE IF NOT EXISTS messages (
    id                  SERIAL PRIMARY KEY,
    message_ref         VARCHAR(40)        NOT NULL UNIQUE,  -- MSG-20260311-123456-001
    conversation_id     INT                NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    direction           message_direction  NOT NULL,
    content             TEXT               NOT NULL,
    channel             channel_type       NOT NULL,
    sender_id           VARCHAR(50),       -- customer_ref or 'ai_agent' or 'human:agent_name'

    -- Sentiment analysis
    sentiment_label     VARCHAR(30),       -- positive | neutral | frustrated | angry
    sentiment_score     NUMERIC(4,3),      -- composite 0.000–1.000
    anger_score         NUMERIC(4,3),
    frustration_score   NUMERIC(4,3),
    urgency_detected    BOOLEAN,
    profanity_detected  BOOLEAN,

    -- Agent metadata (outbound)
    agent_confidence    NUMERIC(4,3),
    kb_section_used     VARCHAR(100),
    processing_time_ms  INT,

    -- Delivery
    delivery_status     VARCHAR(30),       -- delivered | pending | failed
    external_message_id VARCHAR(100),      -- WAMID, Gmail message ID, etc.

    created_at          TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    delivered_at        TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS ix_messages_created_at      ON messages(created_at DESC);
CREATE INDEX IF NOT EXISTS ix_messages_direction       ON messages(direction);


-- =============================================================================
-- TABLE: knowledge_base
-- =============================================================================

CREATE TABLE IF NOT EXISTS knowledge_base (
    id               SERIAL PRIMARY KEY,
    section_id       VARCHAR(100)  NOT NULL UNIQUE,  -- password_reset | api_rate_limits
    title            VARCHAR(500)  NOT NULL,
    content          TEXT          NOT NULL,
    keywords         JSONB         NOT NULL,          -- ["password", "reset", "forgot"]
    tags             JSONB,                           -- ["security", "authentication"]
    channel_hints    JSONB,        -- {"whatsapp": "Short version...", "email": "Long version..."}

    -- Usage analytics
    times_retrieved        INT     NOT NULL DEFAULT 0,
    times_led_to_resolve   INT     NOT NULL DEFAULT 0,
    resolution_rate        NUMERIC(4,3),
    avg_confidence         NUMERIC(4,3),

    is_active        BOOLEAN       NOT NULL DEFAULT TRUE,
    created_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_knowledge_base_section_id ON knowledge_base(section_id);
CREATE INDEX IF NOT EXISTS ix_knowledge_base_keywords   ON knowledge_base USING GIN(keywords);
CREATE INDEX IF NOT EXISTS ix_knowledge_base_is_active  ON knowledge_base(is_active);

DROP TRIGGER IF EXISTS set_knowledge_base_updated_at ON knowledge_base;
CREATE TRIGGER set_knowledge_base_updated_at
    BEFORE UPDATE ON knowledge_base
    FOR EACH ROW EXECUTE PROCEDURE update_updated_at_column();


-- =============================================================================
-- TABLE: agent_metrics
-- =============================================================================

CREATE TABLE IF NOT EXISTS agent_metrics (
    id                      SERIAL PRIMARY KEY,
    metric_date             TIMESTAMP WITH TIME ZONE NOT NULL,  -- window start
    window_hours            INT           NOT NULL DEFAULT 24,  -- 1=hourly, 24=daily

    -- Volume
    tickets_created         INT           NOT NULL DEFAULT 0,
    messages_processed      INT           NOT NULL DEFAULT 0,
    responses_generated     INT           NOT NULL DEFAULT 0,

    -- Outcomes
    escalations             INT           NOT NULL DEFAULT 0,
    resolutions             INT           NOT NULL DEFAULT 0,
    sla_breaches            INT           NOT NULL DEFAULT 0,

    -- Quality
    avg_resolution_time_s   NUMERIC(10,2),
    avg_agent_confidence    NUMERIC(4,3),
    avg_sentiment_score     NUMERIC(4,3),

    -- Breakdown (JSON)
    channel_usage           JSONB,     -- {"email": 12, "whatsapp": 45, "web_form": 8}
    escalation_reasons      JSONB,     -- {"legal_threat": 2, "high_anger_score": 5}

    created_at              TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_agent_metrics_date ON agent_metrics(metric_date DESC);


-- =============================================================================
-- SEED: Knowledge Base (mirrors Stage 1 KB entries)
-- =============================================================================

INSERT INTO knowledge_base (section_id, title, content, keywords, tags) VALUES
(
    'password_reset',
    'Password & Security -> Password Reset',
    'To reset your password: go to app.syncflow.io/login -> Forgot Password -> enter email. Reset link valid for 60 minutes. New password must be 12+ chars with uppercase, number, and symbol. Note: resets all active sessions.',
    '["password", "reset", "forgot", "login", "locked"]',
    '["security", "authentication"]'
),
(
    'two_factor_auth',
    'Password & Security -> Two-Factor Authentication',
    'Enable 2FA: Settings -> Security -> Two-Factor Authentication. If invalid code: sync device time, use fresh code (<30s). Supported apps: Google Authenticator, Authy, 1Password, Microsoft Authenticator.',
    '["2fa", "two-factor", "authenticator", "otp", "verification", "invalid code"]',
    '["security", "authentication"]'
),
(
    'api_errors',
    'API Usage -> API Keys & Error Codes',
    '401 Unauthorized: regenerate key at Settings -> Developer -> API Keys. 403 Forbidden: check key scope. 429 Too Many Requests: wait for X-RateLimit-Reset or upgrade plan. Rate limits: Starter 60/min | Growth 300/min | Business 1000/min.',
    '["api", "key", "401", "403", "429", "rate", "limit", "unauthorized", "forbidden"]',
    '["api", "developer"]'
),
(
    'billing',
    'Billing & Subscriptions',
    'Invoices generated 1st of month (Settings -> Billing -> Invoice History). Upgrades: immediate with prorated charge. Downgrades: next cycle. Refund policy: annual plans within 30 days; monthly plans no current-period refund.',
    '["billing", "invoice", "charge", "payment", "refund", "subscription", "cost", "price"]',
    '["billing", "payments"]'
),
(
    'integrations',
    'Integrations -> Connecting an Integration',
    'Connect: Dashboard -> Integrations -> Browse -> Connect -> OAuth -> Configure. If OAuth fails with redirect_uri_mismatch: clear browser cookies or try a different browser.',
    '["salesforce", "hubspot", "slack", "google", "sheets", "oauth", "connect", "integration"]',
    '["integrations", "oauth"]'
),
(
    'oauth_token_expiry',
    'Integrations -> OAuth Token Expiry',
    'OAuth tokens expire for security. Fix: Integrations -> [App] -> Reconnect -> Re-authorize. Workflows resume automatically after reconnection.',
    '["oauth", "token", "expired", "reconnect", "session", "invalid_session"]',
    '["integrations", "oauth"]'
),
(
    'workflow_trigger',
    'Troubleshooting -> Workflow Not Triggering',
    'If workflow not triggering: 1) Check status is Active. 2) Verify trigger conditions. 3) Check webhook registration. 4) Confirm timezone for scheduled triggers. 5) Check monthly run limit. View history: Workflows -> [Name] -> Run History.',
    '["workflow", "trigger", "not", "firing", "stopped", "scheduled", "paused"]',
    '["workflows", "troubleshooting"]'
),
(
    'webhooks',
    'API Usage -> Webhooks',
    'Duplicate webhooks: endpoint must return 200 within 5 seconds. Retry policy: 1m, 5m, 30m, 2h, 12h. Use X-SyncFlow-Event-ID header for idempotency to deduplicate on your end.',
    '["webhook", "duplicate", "firing", "twice", "multiple", "retry"]',
    '["api", "webhooks", "developer"]'
),
(
    'sso',
    'Password & Security -> Single Sign-On',
    'SSO available on Business and Enterprise plans. Providers: Okta, Azure AD, Google Workspace, OneLogin. Requires Admin access. Common issues: domain mismatch, redirect loop (try incognito).',
    '["sso", "saml", "okta", "azure", "google workspace", "single sign", "login"]',
    '["security", "enterprise"]'
),
(
    'data_export',
    'Data & Privacy -> Exporting Your Data',
    'Export: Settings -> Data -> Export Account Data. Includes workflows, run history, team settings, integration configs. Processing: up to 2 hours. Post-cancellation: data retained 90 days.',
    '["export", "data", "download", "cancel", "cancellation", "delete", "backup"]',
    '["data", "privacy"]'
),
(
    'team_management',
    'Account Management -> Managing Team Members',
    'Roles: Admin (full access), Member (workspace only), Viewer (read-only). Invite: Settings -> Team -> Invite Members. Invites expire 7 days. Seats: Starter 5 | Growth 25 | Business 100 | Enterprise unlimited.',
    '["seat", "member", "invite", "team", "viewer", "admin", "role", "permission"]',
    '["account", "team"]'
),
(
    'workspaces',
    'Account Management -> Workspaces',
    'Workspaces are isolated environments. Create: Dashboard -> New Workspace. Limits: Starter 3 | Growth 10 | Business/Enterprise unlimited.',
    '["workspace", "department", "project", "client", "isolated"]',
    '["account"]'
)
ON CONFLICT (section_id) DO NOTHING;

-- =============================================================================
-- SEED: Sample Customers (mirrors Stage 1 mock data)
-- =============================================================================

INSERT INTO customers (customer_ref, name, plan, is_vip, account_health, mrr, csat_average, total_tickets, account_created) VALUES
    ('C-1042', 'Marcus Chen',    'growth',    FALSE, 'healthy',  99.00, 4.6,  3, '2024-03-15'),
    ('C-2817', 'Priya Nair',     'starter',   FALSE, 'healthy',  29.00, NULL, 1, '2025-01-10'),
    ('C-3301', 'James Whitfield','business',  FALSE, 'healthy', 299.00, 4.2,  8, '2023-07-22'),
    ('C-4451', 'Sofia Reyes',    'growth',    FALSE, 'at_risk',  99.00, 3.8,  5, '2025-06-01'),
    ('C-6229', 'Lena Hoffmann',  'business',  TRUE,  'healthy', 299.00, 4.9, 12, '2022-11-05'),
    ('C-8901', 'Angela Torres',  'enterprise',TRUE,  'healthy', 999.00, 4.8,  2, '2023-01-15')
ON CONFLICT (customer_ref) DO NOTHING;

-- Seed customer identifiers
WITH cust AS (SELECT id, customer_ref FROM customers)
INSERT INTO customer_identifiers (customer_id, identifier_type, identifier_value, is_primary)
SELECT c.id, 'email', v.email, TRUE
FROM cust c
JOIN (VALUES
    ('C-1042', 'marcus.chen@acme.io'),
    ('C-2817', 'priya.nair@startup.io'),
    ('C-3301', 'j.whitfield@techbridge.com'),
    ('C-4451', 's.reyes@marketingco.com'),
    ('C-6229', 'l.hoffmann@enterprise-solutions.de'),
    ('C-8901', 'a.torres@globalcorp.com')
) AS v(customer_ref, email) ON c.customer_ref = v.customer_ref
ON CONFLICT ON CONSTRAINT uq_identifier DO NOTHING;
