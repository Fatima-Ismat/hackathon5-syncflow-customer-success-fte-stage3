"""
database/seed.py
SyncFlow Customer Success Digital FTE — Stage 3

Seeds the database with demo customers and knowledge base articles.

Usage:
  python database/seed.py
  python -m database.seed
"""

import sys
import os
import logging

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

logger = logging.getLogger("syncflow.seed")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


SEED_CUSTOMERS = [
    {
        "customer_ref": "C-1042",
        "name": "Alice Chen",
        "company": "Acme Corp",
        "email": "alice@acmecorp.com",
        "phone": "+14155550101",
        "plan": "business",
        "is_vip": True,
        "account_health": "healthy",
        "mrr": 2500.0,
    },
    {
        "customer_ref": "C-2071",
        "name": "Bob Martinez",
        "company": "Startup Inc",
        "email": "bob@startupinc.com",
        "phone": "+14155550102",
        "plan": "growth",
        "is_vip": False,
        "account_health": "healthy",
        "mrr": 450.0,
    },
    {
        "customer_ref": "C-3388",
        "name": "Carol Williams",
        "company": "Enterprise Ltd",
        "email": "carol@enterpriseltd.com",
        "phone": "+14155550103",
        "plan": "enterprise",
        "is_vip": True,
        "account_health": "healthy",
        "mrr": 8000.0,
    },
    {
        "customer_ref": "C-4459",
        "name": "David Kim",
        "company": "Solo Dev",
        "email": "david@solodev.io",
        "phone": "+14155550104",
        "plan": "starter",
        "is_vip": False,
        "account_health": "at_risk",
        "mrr": 49.0,
    },
    {
        "customer_ref": "C-5521",
        "name": "Emma Johnson",
        "company": "MidMarket Co",
        "email": "emma@midmarketco.com",
        "phone": "+14155550105",
        "plan": "growth",
        "is_vip": False,
        "account_health": "healthy",
        "mrr": 890.0,
    },
    {
        "customer_ref": "C-6634",
        "name": "Frank Okonkwo",
        "company": "Scale Fast LLC",
        "email": "frank@scalefast.io",
        "phone": "+14155550106",
        "plan": "business",
        "is_vip": False,
        "account_health": "healthy",
        "mrr": 1800.0,
    },
    {
        "customer_ref": "C-8901",
        "name": "Grace Liu",
        "company": "TechCorp Global",
        "email": "grace@techcorpglobal.com",
        "phone": "+14155550107",
        "plan": "enterprise",
        "is_vip": True,
        "account_health": "healthy",
        "mrr": 15000.0,
    },
]


SEED_KB = [
    {
        "section": "authentication",
        "title": "Password Reset",
        "content": (
            "To reset your SyncFlow password: go to app.syncflow.io/forgot-password, "
            "enter your email address, and click 'Send Reset Link'. The reset link expires "
            "in 15 minutes. Check your spam/junk folder if you don't see it within 2 minutes. "
            "If the link is expired, request a new one. Admins can also reset passwords for "
            "team members from Settings > Team Management > [User] > Reset Password."
        ),
        "tags": "password,reset,login,forgot,email,link,expire",
    },
    {
        "section": "authentication",
        "title": "Two-Factor Authentication (2FA)",
        "content": (
            "SyncFlow supports 2FA via authenticator app (Google Authenticator, Authy) or SMS. "
            "To enable: Settings > Security > Two-Factor Authentication > Enable. "
            "Download backup codes immediately after setup — store them safely. "
            "If you lose access to your authenticator: use a backup code or contact your "
            "account admin to temporarily disable 2FA. SMS 2FA may have delivery delays; "
            "authenticator app is recommended."
        ),
        "tags": "2fa,two-factor,mfa,authenticator,sms,security,backup codes",
    },
    {
        "section": "api",
        "title": "API Error Codes",
        "content": (
            "Common SyncFlow API errors: "
            "401 Unauthorized — API key missing or invalid; regenerate at Settings > API Keys. "
            "403 Forbidden — insufficient permissions for this resource. "
            "429 Too Many Requests — rate limit exceeded; Starter: 100 req/min, "
            "Growth: 500 req/min, Business: 2000 req/min, Enterprise: unlimited. "
            "500 Internal Server Error — retry with exponential backoff (max 3 attempts). "
            "422 Unprocessable Entity — invalid request body; check the API docs. "
            "All errors return JSON: {error: string, code: string, docs_url: string}."
        ),
        "tags": "api,error,401,403,429,500,rate limit,unauthorized,forbidden",
    },
    {
        "section": "billing",
        "title": "Billing and Subscription Management",
        "content": (
            "To cancel: Settings > Billing > Cancel Subscription. 30-day notice required; "
            "access continues until end of billing period. Upgrades take effect immediately "
            "with prorated charge. Downgrades apply at next billing cycle. "
            "Invoices are emailed on billing date and available at Settings > Billing > Invoices. "
            "We accept Visa, Mastercard, American Express, and ACH transfers (Enterprise). "
            "Refunds for annual plans: prorated if cancelled within 30 days. Monthly plans "
            "are non-refundable after the billing date. Contact billing@syncflow.io for disputes."
        ),
        "tags": "billing,invoice,cancel,refund,subscription,upgrade,downgrade,payment",
    },
    {
        "section": "integrations",
        "title": "Third-Party Integrations",
        "content": (
            "SyncFlow integrates with: Slack (send notifications to channels), "
            "GitHub (trigger workflows on PR/issue events), Jira (create/update issues), "
            "Salesforce (sync customer data), HubSpot (CRM sync), Zapier (connect 5000+ apps). "
            "To configure: Settings > Integrations > [Service] > Connect. "
            "OAuth-based integrations require re-authorization every 60 days. "
            "Webhook integrations: provide your endpoint URL; SyncFlow signs payloads with "
            "HMAC-SHA256 (header: X-SyncFlow-Signature)."
        ),
        "tags": "integration,slack,github,jira,salesforce,zapier,webhook,oauth,connect",
    },
    {
        "section": "workflows",
        "title": "Workflow Automation",
        "content": (
            "Workflows automate multi-step processes triggered by events. "
            "Trigger types: Schedule (cron), Webhook, API call, Data change, Manual. "
            "Action limits: Starter 500/day, Growth 5,000/day, Business 50,000/day, "
            "Enterprise unlimited. To create: Workflows > New Workflow > Add Trigger > Add Steps. "
            "Debug mode lets you test with sample data. "
            "Failed workflows retry 3 times with exponential backoff, then move to 'Failed' status. "
            "View execution logs in Workflows > [Workflow] > Run History."
        ),
        "tags": "workflow,automation,trigger,action,limit,schedule,webhook,retry,logs",
    },
    {
        "section": "security",
        "title": "SSO and Enterprise Security",
        "content": (
            "Single Sign-On (SSO) is available on Business and Enterprise plans. "
            "Supported protocols: SAML 2.0, OpenID Connect (OIDC). "
            "Providers: Okta, Azure AD, Google Workspace, OneLogin, custom IdP. "
            "To configure: Settings > Security > SSO > Configure. You'll need your IdP metadata URL. "
            "SCIM provisioning available for automatic user sync (Enterprise only). "
            "Audit logs available at Settings > Security > Audit Log (90-day retention on Business, "
            "1-year on Enterprise)."
        ),
        "tags": "sso,saml,oidc,security,okta,azure,google,enterprise,scim,audit",
    },
    {
        "section": "data",
        "title": "Data Export",
        "content": (
            "Export your data at any time from Settings > Data Management > Export. "
            "Available formats: CSV, JSON, Excel. "
            "Export scope: Workflows, Execution logs, Customer data, API usage. "
            "Large exports (>100MB) are processed asynchronously; you'll receive an email "
            "with a download link within 1 hour. Export links expire after 48 hours. "
            "For GDPR data portability requests or complete account data deletion, "
            "contact privacy@syncflow.io with subject 'Data Request - [Company Name]'."
        ),
        "tags": "export,data,csv,json,gdpr,download,backup,portability",
    },
    {
        "section": "team",
        "title": "Team Management",
        "content": (
            "Invite team members: Settings > Team > Invite Member > enter email. "
            "Roles: Owner (full access, billing), Admin (all features except billing), "
            "Member (create/run workflows), Viewer (read-only). "
            "Owner can transfer ownership to any Admin. "
            "Remove members: Settings > Team > [Member] > Remove. Their workflows remain but "
            "are reassigned to the Owner. SSO users are provisioned/deprovisioned automatically "
            "(Enterprise with SCIM). Guest access: share specific workflow results via public links."
        ),
        "tags": "team,invite,member,role,owner,admin,viewer,permissions,access",
    },
    {
        "section": "workspaces",
        "title": "Workspaces",
        "content": (
            "Workspaces provide separate environments for different teams/projects. "
            "Each workspace has its own: members, workflows, integrations, billing, and data. "
            "Create a workspace: click your workspace name in top-left > New Workspace. "
            "Switch workspaces from the same dropdown. "
            "On Enterprise plans, workspaces can share an SSO configuration. "
            "Billing is per-workspace — each workspace requires its own subscription. "
            "To merge workspaces, contact support@syncflow.io."
        ),
        "tags": "workspace,environment,separate,billing,team,switch,merge",
    },
    {
        "section": "webhooks",
        "title": "Webhooks Configuration",
        "content": (
            "Webhooks let SyncFlow notify your system of events in real time. "
            "Configure at Settings > Integrations > Webhooks > Add Webhook. "
            "Events: workflow.run.completed, workflow.run.failed, user.created, "
            "ticket.created, ticket.escalated. "
            "SyncFlow retries failed webhooks 3 times with exponential backoff: "
            "1min, 5min, 30min. After 3 failures, webhook is marked 'failing'. "
            "View webhook logs at Settings > Integrations > Webhooks > [Webhook] > Logs. "
            "Validate payloads using the X-SyncFlow-Signature HMAC-SHA256 header."
        ),
        "tags": "webhook,event,notification,retry,signature,hmac,logs,configuration",
    },
    {
        "section": "oauth",
        "title": "OAuth Token Management",
        "content": (
            "OAuth access tokens expire every 60 minutes. SyncFlow automatically refreshes "
            "tokens before expiry using the refresh token (valid 30 days). "
            "If you see 'OAuth token expired' errors: re-authenticate via Settings > "
            "Integrations > [Service] > Reconnect. "
            "For server-side apps, use API Keys instead of OAuth for long-lived access. "
            "OAuth scopes: read, write, admin — request only the scopes your app needs. "
            "Revoking access: Settings > Security > Connected Apps > Revoke."
        ),
        "tags": "oauth,token,expire,refresh,authentication,reconnect,scope,revoke",
    },
]


def seed_database():
    """Populate the database with demo data."""
    try:
        from database.connection import SessionLocal, init_db
        from database.queries import get_customer_by_ref, create_customer

        init_db()
        db = SessionLocal()

        # Seed customers
        created_customers = 0
        for cdata in SEED_CUSTOMERS:
            existing = get_customer_by_ref(db, cdata["customer_ref"])
            if not existing:
                create_customer(db, cdata)
                created_customers += 1
                logger.info("Created customer: %s (%s)", cdata["customer_ref"], cdata["name"])

        # Seed knowledge base
        from database.models import KnowledgeBase
        created_kb = 0
        for kb_data in SEED_KB:
            existing = db.query(KnowledgeBase).filter(
                KnowledgeBase.section == kb_data["section"],
                KnowledgeBase.title == kb_data["title"],
            ).first()
            if not existing:
                kb = KnowledgeBase(**kb_data, usage_count=0)
                db.add(kb)
                created_kb += 1

        db.commit()
        db.close()

        logger.info("Seed complete: %d customers, %d KB articles", created_customers, created_kb)
        return {"customers": created_customers, "kb_articles": created_kb}

    except Exception as e:
        logger.error("Seed failed: %s", e)
        return {"error": str(e)}


if __name__ == "__main__":
    result = seed_database()
    print(result)
