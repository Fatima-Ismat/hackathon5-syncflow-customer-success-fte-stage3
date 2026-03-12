"""
agent/tools.py
NovaSync Technologies / SyncFlow — Customer Success Digital FTE
Stage 3: OpenAI Agents SDK-compatible function tools.

Architecture
------------
Each tool has two layers:

1. A private ``_impl_*`` function containing the real business logic.
   These are always plain Python callables, usable directly by the
   fallback orchestration path in ``customer_success_agent.py``.

2. A public SDK-registered version created with ``function_tool()``.
   When the ``openai-agents`` package is installed these become
   ``FunctionTool`` objects that the SDK Runner can call autonomously.
   When the package is NOT installed they remain plain Python callables
   (a no-op decorator is applied instead).

The public names (``search_knowledge_base``, ``analyze_sentiment``, …)
are the SDK-wrapped versions and belong in ``ALL_TOOLS``.
The orchestration code calls the ``_impl_*`` variants directly so it
never receives a non-callable ``FunctionTool`` object.

Tool inventory
--------------
1. search_knowledge_base / _impl_search_knowledge_base
2. get_customer_history  / _impl_get_customer_history
3. create_ticket         / _impl_create_ticket
4. escalate_to_human     / _impl_escalate_to_human
5. analyze_sentiment     / _impl_analyze_sentiment
6. update_ticket_status  / _impl_update_ticket_status
"""

from __future__ import annotations

import logging
import random
import re
import uuid
from datetime import datetime, timedelta, timezone
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# SDK detection — SDK wrapper vs. no-op
# ---------------------------------------------------------------------------

try:
    from agents import function_tool as _sdk_function_tool  # type: ignore[import]
    _AGENTS_SDK = True
    logger.info("tools: OpenAI Agents SDK detected — wrapping tools with @function_tool")
except ImportError:
    _AGENTS_SDK = False
    logger.info("tools: OpenAI Agents SDK not found — tools remain plain callables")

    def _sdk_function_tool(func: Callable) -> Callable:  # type: ignore[misc]
        """No-op decorator when openai-agents is not installed."""
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            return func(*args, **kwargs)
        wrapper.__is_tool__ = True  # type: ignore[attr-defined]
        return wrapper


# ---------------------------------------------------------------------------
# In-memory knowledge base (SyncFlow product documentation)
# ---------------------------------------------------------------------------

_KB_ENTRIES: list[dict[str, Any]] = [
    {
        "keywords": {"password", "reset", "forgot", "link", "locked", "login", "expire"},
        "section": "Password & Security -> Password Reset",
        "answer": (
            "To reset your SyncFlow password:\n"
            "1. Navigate to app.syncflow.io/login\n"
            "2. Click 'Forgot Password' beneath the sign-in form\n"
            "3. Enter the email address linked to your account\n"
            "4. Click 'Send Reset Link'\n"
            "5. Open the email from noreply@syncflow.io — the link is valid for 15 minutes\n"
            "6. Create a new password (minimum 12 characters, at least one uppercase letter, "
            "one number, and one special character)\n\n"
            "Important: The reset link expires after 15 minutes. If it has expired, repeat "
            "the process. Check your spam/junk folder if the email has not arrived. "
            "If you no longer have access to the registered email, your Workspace Owner can "
            "reset your account via Settings -> Team -> Members."
        ),
        "confidence_base": 0.90,
    },
    {
        "keywords": {"2fa", "two-factor", "two factor", "authenticator", "otp", "mfa",
                     "verification code", "backup code", "sms", "totp"},
        "section": "Password & Security -> Two-Factor Authentication",
        "answer": (
            "Setting up or troubleshooting Two-Factor Authentication (2FA):\n\n"
            "Enable 2FA: Settings -> Security -> Two-Factor Authentication -> Enable\n"
            "Supported methods: Authenticator app (Google Authenticator, Authy, 1Password, "
            "Microsoft Authenticator) or SMS to a verified phone number.\n\n"
            "Backup codes: During 2FA setup you are shown 10 single-use backup codes. "
            "Store them securely. Regenerate at Settings -> Security -> 2FA -> Backup Codes.\n\n"
            "Troubleshooting 'invalid code':\n"
            "1. Confirm your device clock is accurate (authenticator apps are time-sensitive)\n"
            "2. Use the most recently generated code — codes refresh every 30 seconds\n"
            "3. If using SMS, allow up to 60 seconds for network delivery\n"
            "4. If locked out without backup codes, contact support for identity verification"
        ),
        "confidence_base": 0.88,
    },
    {
        "keywords": {"api", "key", "401", "403", "429", "rate limit", "rate-limit",
                     "unauthorized", "forbidden", "token", "developer", "endpoint"},
        "section": "API Usage -> API Keys & Error Codes",
        "answer": (
            "SyncFlow API — common error codes:\n\n"
            "401 Unauthorized — API key is invalid, revoked, or expired.\n"
            "  Fix: Regenerate your key at Settings -> Developer -> API Keys.\n\n"
            "403 Forbidden — the key is valid but lacks permission for this resource.\n"
            "  Fix: Check the key's allowed scopes; create a new key with the required scope.\n\n"
            "429 Too Many Requests — rate limit exceeded.\n"
            "  Fix: Back off and retry after the time in the Retry-After response header.\n"
            "  Rate limits by plan: Starter 60 req/min | Growth 300 req/min | "
            "Business 1,000 req/min\n\n"
            "API base URL: https://api.syncflow.io/v2\n"
            "Full reference: syncflow.io/docs/api"
        ),
        "confidence_base": 0.91,
    },
    {
        "keywords": {"billing", "invoice", "charge", "payment", "subscription",
                     "plan", "upgrade", "downgrade", "prorate", "cost", "price",
                     "cancel", "cancellation"},
        "section": "Billing & Subscriptions",
        "answer": (
            "SyncFlow billing information:\n\n"
            "Invoices are generated on the 1st of each month and emailed to the Billing Owner.\n"
            "View past invoices: Settings -> Billing -> Invoice History.\n\n"
            "Upgrading a plan takes effect immediately with a prorated charge for the remaining "
            "days in the current cycle.\n\n"
            "Downgrading takes effect at the start of the next billing cycle.\n\n"
            "Cancellation: 30 days written notice required (Settings -> Billing -> "
            "Cancel Subscription or email billing@novasynctechnologies.com). "
            "Account data is retained for 90 days after cancellation.\n\n"
            "Refunds: Annual plans — prorated refund within 30 days of purchase. "
            "Monthly plans — no refund for the current period.\n\n"
            "For billing disputes, contact billing@novasynctechnologies.com."
        ),
        "confidence_base": 0.87,
    },
    {
        "keywords": {"slack", "github", "jira", "salesforce", "hubspot", "google",
                     "integration", "connect", "oauth", "authorize"},
        "section": "Integrations -> Connecting an Integration",
        "answer": (
            "SyncFlow supports native integrations with: Slack, GitHub, Jira, Salesforce, "
            "HubSpot, Google Workspace, Microsoft 365, and more.\n\n"
            "To connect an integration:\n"
            "1. Go to Dashboard -> Integrations -> Browse Integrations\n"
            "2. Search for the app and click Connect\n"
            "3. Authorise access via OAuth (you will be redirected to the external service)\n"
            "4. Configure field mapping and sync frequency\n"
            "5. Click Test Connection to verify\n\n"
            "Common OAuth error — 'redirect_uri_mismatch':\n"
            "Clear browser cookies and cache, then retry in a private window.\n"
            "Confirm the redirect URI in the external app matches "
            "https://app.syncflow.io/oauth/callback"
        ),
        "confidence_base": 0.85,
    },
    {
        "keywords": {"oauth", "token", "expired", "reconnect", "session", "re-auth",
                     "reauthorize", "reconnect required"},
        "section": "Integrations -> OAuth Token Expiry",
        "answer": (
            "OAuth tokens for SyncFlow integrations refresh automatically every 60 minutes. "
            "If the token cannot be refreshed, you will see a 'Reconnect Required' banner.\n\n"
            "To fix:\n"
            "1. Go to Integrations -> [App Name] -> Settings\n"
            "2. Click Reconnect\n"
            "3. Re-authorise with your credentials in the external service\n"
            "4. Your workflows will resume automatically within 60 seconds\n\n"
            "Tip: Tokens are per-user. If multiple team members use the integration, "
            "each must reconnect individually."
        ),
        "confidence_base": 0.82,
    },
    {
        "keywords": {"workflow", "trigger", "firing", "stopped", "not running",
                     "paused", "scheduled", "automation", "run limit", "run history"},
        "section": "Workflows -> Troubleshooting Workflows",
        "answer": (
            "If your workflow is not triggering:\n\n"
            "1. Check the workflow status — it must be Active (not Paused or Draft).\n"
            "   Workflows -> [Name] -> Status toggle.\n\n"
            "2. Verify the trigger conditions are correctly configured.\n\n"
            "3. For webhook triggers: confirm the source app's webhook is still registered "
            "and pointing to your SyncFlow webhook URL.\n\n"
            "4. For scheduled triggers: check the timezone setting matches your intent.\n\n"
            "5. Check your plan's daily automation run limit:\n"
            "   Starter 500 actions/day | Growth 5,000/day | Business+ unlimited\n\n"
            "View run history: Workflows -> [Name] -> Run History"
        ),
        "confidence_base": 0.86,
    },
    {
        "keywords": {"webhook", "duplicate", "twice", "multiple times", "retry",
                     "exponential", "backoff", "idempotent", "event id"},
        "section": "API Usage -> Webhooks",
        "answer": (
            "SyncFlow webhooks use exponential-backoff retry logic:\n"
            "Attempt 1: immediate | Attempt 2: 1 min later | Attempt 3: 5 min later\n"
            "After 3 failed attempts the event is marked failed with no further retries.\n\n"
            "Duplicate events occur when your endpoint does not return HTTP 200 within 5 seconds.\n\n"
            "Best practices:\n"
            "Respond immediately with 200 OK, then process asynchronously.\n"
            "Use the X-SyncFlow-Event-ID header to implement idempotency — "
            "discard events with IDs your system has already processed.\n\n"
            "Webhook logs: Settings -> Developer -> Webhook Logs"
        ),
        "confidence_base": 0.84,
    },
    {
        "keywords": {"sso", "saml", "okta", "azure", "google workspace", "onelogin",
                     "single sign-on", "single sign on", "identity provider"},
        "section": "Password & Security -> Single Sign-On (SSO)",
        "answer": (
            "SSO via SAML 2.0 is available on Business and Enterprise plans only.\n\n"
            "Supported identity providers: Okta, Azure Active Directory, "
            "Google Workspace, OneLogin.\n\n"
            "Configuration: Settings -> Security -> Single Sign-On -> Configure SSO\n"
            "You will need your IdP metadata URL or XML file.\n\n"
            "Common issues:\n"
            "SSO not enabled on your plan: upgrade to Business or Enterprise.\n"
            "Email domain mismatch: user email domain must match the configured SSO domain.\n"
            "Redirect loop: clear cookies and retry in an incognito window.\n"
            "NameID not found: ensure your IdP sends the email as the NameID attribute.\n\n"
            "SSO configuration requires Owner or Admin access."
        ),
        "confidence_base": 0.89,
    },
    {
        "keywords": {"export", "data export", "download", "csv", "json",
                     "backup", "settings export", "account data"},
        "section": "Data & Privacy -> Exporting Your Data",
        "answer": (
            "To export your SyncFlow account data:\n"
            "1. Settings -> Data -> Export Account Data\n"
            "2. Select data types (workflows, run history, team settings, "
            "integration configs, custom fields)\n"
            "3. Choose format: CSV or JSON\n"
            "4. Click Request Export\n"
            "5. You will receive a download link by email within 2 hours\n\n"
            "Post-cancellation: All account data is retained for 90 days before permanent deletion. "
            "Export your data before this window closes."
        ),
        "confidence_base": 0.87,
    },
    {
        "keywords": {"team", "member", "invite", "seat", "role", "permission",
                     "owner", "admin", "viewer", "remove", "deactivate"},
        "section": "Account Management -> Managing Team Members",
        "answer": (
            "SyncFlow team roles:\n"
            "Owner: full access including billing and account deletion (1 per account)\n"
            "Admin: full access except billing and transferring ownership\n"
            "Member: access to assigned workspaces only\n"
            "Viewer: read-only access to shared dashboards\n\n"
            "To invite a team member:\n"
            "Settings -> Team -> Invite Members -> Enter email -> Select role -> Send Invite\n"
            "Invitations expire after 7 days.\n\n"
            "Seat limits: Starter 5 | Growth 25 | Business 100 | Enterprise unlimited\n\n"
            "To remove: Settings -> Team -> Members -> [Name] -> Remove"
        ),
        "confidence_base": 0.88,
    },
    {
        "keywords": {"workspace", "workspaces", "department", "project",
                     "client workspace", "isolated", "separate billing"},
        "section": "Account Management -> Workspaces",
        "answer": (
            "Workspaces are isolated environments within your SyncFlow account — "
            "separate member lists, workflows, and billing.\n\n"
            "Create limits by plan:\n"
            "Starter: up to 3 workspaces | Growth: up to 10 | Business/Enterprise: unlimited\n\n"
            "To create a workspace:\n"
            "Dashboard -> New Workspace -> Name it -> Set member permissions -> Create\n\n"
            "Each workspace has its own Owner role. Billing rolls up to the account level "
            "unless per-workspace billing is enabled (Enterprise only)."
        ),
        "confidence_base": 0.85,
    },
]


# ---------------------------------------------------------------------------
# In-memory ticket store and customer seed data
# ---------------------------------------------------------------------------

_TICKET_STORE: dict[str, dict[str, Any]] = {}

_CUSTOMER_DB: dict[str, dict[str, Any]] = {
    "C-1042": {
        "customer_ref": "C-1042",
        "name": "Marcus Chen",
        "email": "m.chen@devstudio.io",
        "plan": "growth",
        "account_health": "good",
        "is_vip": False,
        "mrr": 299,
        "recent_tickets": [
            {
                "ticket_ref": "TKT-20260201-7731",
                "subject": "API 429 rate limit",
                "status": "resolved",
                "created_at": "2026-02-01T09:12:00Z",
            }
        ],
    },
    "C-2817": {
        "customer_ref": "C-2817",
        "name": "Priya Nair",
        "email": "priya@aibootcamp.co",
        "plan": "starter",
        "account_health": "good",
        "is_vip": False,
        "mrr": 49,
        "recent_tickets": [],
    },
    "C-3301": {
        "customer_ref": "C-3301",
        "name": "James Whitfield",
        "email": "j.whitfield@techbridge.com",
        "plan": "business",
        "account_health": "good",
        "is_vip": False,
        "mrr": 999,
        "recent_tickets": [
            {
                "ticket_ref": "TKT-20260115-2245",
                "subject": "Unexpected billing charge",
                "status": "resolved",
                "created_at": "2026-01-15T14:30:00Z",
            }
        ],
    },
    "C-4451": {
        "customer_ref": "C-4451",
        "name": "Sofia Reyes",
        "email": "sofia@greenleaf.design",
        "plan": "growth",
        "account_health": "at_risk",
        "is_vip": False,
        "mrr": 299,
        "recent_tickets": [
            {
                "ticket_ref": "TKT-20260220-9912",
                "subject": "Workflow not triggering",
                "status": "open",
                "created_at": "2026-02-20T10:05:00Z",
            },
            {
                "ticket_ref": "TKT-20260207-3318",
                "subject": "Slack integration OAuth error",
                "status": "resolved",
                "created_at": "2026-02-07T16:00:00Z",
            },
        ],
    },
    "C-5103": {
        "customer_ref": "C-5103",
        "name": "David Okafor",
        "email": "david.o@ngstartup.ng",
        "plan": "starter",
        "account_health": "at_risk",
        "is_vip": False,
        "mrr": 49,
        "recent_tickets": [
            {
                "ticket_ref": "TKT-20260218-6621",
                "subject": "Cannot log in",
                "status": "open",
                "created_at": "2026-02-18T08:50:00Z",
            },
            {
                "ticket_ref": "TKT-20260210-5509",
                "subject": "2FA code not working",
                "status": "resolved",
                "created_at": "2026-02-10T13:20:00Z",
            },
        ],
    },
    "C-6229": {
        "customer_ref": "C-6229",
        "name": "Lena Hoffmann",
        "email": "lena.h@acme-corp.de",
        "plan": "business",
        "account_health": "good",
        "is_vip": True,
        "mrr": 999,
        "recent_tickets": [],
    },
    "C-8901": {
        "customer_ref": "C-8901",
        "name": "Angela Torres",
        "email": "a.torres@globalops.com",
        "plan": "enterprise",
        "account_health": "good",
        "is_vip": True,
        "mrr": 4999,
        "recent_tickets": [
            {
                "ticket_ref": "TKT-20260301-1144",
                "subject": "SSO SAML configuration",
                "status": "resolved",
                "created_at": "2026-03-01T09:00:00Z",
            }
        ],
    },
}

# SLA map: plan -> hours to resolve
_SLA_HOURS: dict[str, int] = {
    "starter":    24,
    "growth":     8,
    "business":   2,
    "enterprise": 1,
}

# Escalation queue routing
_ESCALATION_QUEUES: dict[str, str] = {
    "legal_threat":                    "legal-team",
    "legal":                           "legal-team",
    "lawsuit":                         "legal-team",
    "attorney":                        "legal-team",
    "security_incident":               "security-team",
    "hacked":                          "security-team",
    "security_breach":                 "security-team",
    "data_breach":                     "security-team",
    "account_compromise":              "security-team",
    "refund":                          "billing-team",
    "refund_request":                  "billing-team",
    "billing_dispute":                 "billing-team",
    "pricing_negotiation":             "sales-team",
    "contract_negotiation":            "sales-team",
    "enterprise_renewal":              "sales-team",
    "cancellation_churn_risk":         "sales-team",
    "high_anger_score":                "senior-support",
    "anger":                           "senior-support",
    "persistent_frustration":          "senior-support",
    "profanity_detected":              "senior-support",
    "vip_customer_negative_sentiment": "senior-support",
    "vip_unresolved":                  "senior-support",
    "low_kb_confidence":               "technical-support",
    "agent_error":                     "technical-support",
    "technical":                       "technical-support",
    "unresolved_after_multiple_turns": "general-support",
    "talk_to_human":                   "general-support",
    "explicit_escalation_request":     "general-support",
    "agent_unavailable":               "general-support",
}

# Sentiment keyword patterns
_ANGER_PATTERNS: list[str] = [
    r"\bridiculous\b", r"\bunacceptable\b", r"\bfurious\b", r"\boutraged\b",
    r"\blawsuit\b", r"\blawyer\b", r"\battorney\b", r"\blegal action\b",
    r"\bdisgraceful\b", r"\bdisgusting\b", r"\bterrible\b", r"\bawful\b",
    r"\bpathetic\b", r"\buseless\b", r"\bscam\b", r"\bfraud\b",
    r"\bbroken\b", r"\bworst\b", r"\bhate\b", r"\bstupid\b",
    r"\bincompetent\b", r"\bnightmare\b", r"\bappalling\b",
]
_FRUSTRATION_PATTERNS: list[str] = [
    r"\bstill\b", r"\bagain\b", r"\bdays?\b", r"\bhours?\b",
    r"\bwaiting\b", r"\bno response\b", r"\bnothing works\b",
    r"\bkeeps? failing\b", r"\bsame issue\b", r"\bnot fixed\b",
    r"\bbeen trying\b", r"\bmultiple times\b", r"\bover and over\b",
    r"\bno one\b", r"\bnobody\b", r"\bignored\b", r"\bforgotten\b",
    r"\bdisappointed\b", r"\bfrustrated\b", r"\bunable to\b",
]
_URGENCY_PATTERNS: list[str] = [
    r"\burgent\b", r"\basap\b", r"\bimmediately\b", r"\bright now\b",
    r"\blosing money\b", r"\bshut down\b", r"\bcritical\b",
    r"\bemergency\b", r"\boutage\b", r"\bproduction down\b",
    r"\bblocking\b", r"\bdeadline\b", r"\bcan't wait\b",
]
_PROFANITY_PATTERNS: list[str] = [
    r"\bdamn\b", r"\bhell\b", r"\bcrap\b", r"\bshit\b",
    r"\bfuck\b", r"\bbastard\b", r"\bidiot\b", r"\bmoron\b",
    r"\bbullshit\b",
]


# ===========================================================================
# Tool implementations — private ``_impl_*`` callables
# All business logic lives here.  These are ALWAYS plain Python functions.
# ===========================================================================


def _impl_search_knowledge_base(query: str, channel: str = "web_form") -> dict[str, Any]:
    """
    Search the SyncFlow knowledge base for an authoritative answer.

    Uses multi-signal keyword matching with a confidence scorer.

    Returns
    -------
    dict: found, section, answer, confidence, keywords_matched
    """
    logger.debug("_impl_search_knowledge_base | query=%r | channel=%s", query[:80], channel)

    if not query or not query.strip():
        return {"found": False, "section": "", "answer": "", "confidence": 0.0,
                "keywords_matched": []}

    query_lower = query.lower()
    query_tokens = set(re.findall(r"\b\w[\w\-]*\b", query_lower))

    scored: list[tuple[float, dict[str, Any]]] = []

    for entry in _KB_ENTRIES:
        keywords: set[str] = entry["keywords"]
        overlap: set[str] = set()

        overlap.update(query_tokens & keywords)
        for kw in keywords:
            if " " in kw and kw in query_lower:
                overlap.add(kw)

        if not overlap:
            continue

        score = len(overlap) / max(len(keywords), 1)
        for kw in overlap:
            if kw in query_lower:
                score += 0.12
        if len(query_tokens) > 5 and len(overlap) >= 2:
            score += 0.08

        score = min(score * entry.get("confidence_base", 0.85), 1.0)
        scored.append((round(score, 3), entry))

    if not scored:
        logger.debug("_impl_search_knowledge_base | no KB match")
        return {"found": False, "section": "", "answer": "", "confidence": 0.10,
                "keywords_matched": []}

    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_entry = scored[0]
    keywords_matched = sorted(query_tokens & best_entry["keywords"])

    result = {
        "found": best_score >= 0.30,
        "section": best_entry["section"],
        "answer": best_entry["answer"],
        "confidence": best_score,
        "keywords_matched": keywords_matched,
    }
    logger.info(
        "_impl_search_knowledge_base | section=%s | confidence=%.2f | found=%s",
        result["section"], result["confidence"], result["found"],
    )
    return result


def _impl_get_customer_history(customer_ref: str) -> dict[str, Any]:
    """
    Retrieve customer profile and support history from the CRM store.

    Returns
    -------
    dict: found, customer, recent_tickets, account_health
    """
    logger.debug("_impl_get_customer_history | customer_ref=%s", customer_ref)

    customer = _CUSTOMER_DB.get(customer_ref)

    if customer is None:
        logger.info("_impl_get_customer_history | %s not in DB — returning default", customer_ref)
        return {
            "found": False,
            "customer": {
                "customer_ref": customer_ref,
                "name": "Valued Customer",
                "email": None,
                "plan": "starter",
                "account_health": "good",
                "is_vip": False,
                "mrr": 0,
            },
            "recent_tickets": [],
            "account_health": "good",
        }

    return {
        "found": True,
        "customer": {k: v for k, v in customer.items() if k != "recent_tickets"},
        "recent_tickets": customer.get("recent_tickets", []),
        "account_health": customer.get("account_health", "good"),
    }


def _impl_create_ticket(
    customer_ref: str,
    subject: str,
    channel: str,
    priority: str,
    message: str,
) -> dict[str, Any]:
    """
    Create a support ticket with SLA deadline and persist to in-memory store.

    Returns
    -------
    dict: ticket_ref, created_at, sla_deadline, status, priority, channel
    """
    logger.debug(
        "_impl_create_ticket | customer_ref=%s | channel=%s | priority=%s",
        customer_ref, channel, priority,
    )

    customer_data = _CUSTOMER_DB.get(customer_ref, {})
    plan = customer_data.get("plan", "starter")
    sla_hours = _SLA_HOURS.get(plan, 24)

    now_utc = datetime.now(timezone.utc)
    sla_deadline = now_utc + timedelta(hours=sla_hours)

    date_str = now_utc.strftime("%Y%m%d")
    suffix = random.randint(1000, 9999)
    ticket_ref = f"TKT-{date_str}-{suffix}"

    ticket = {
        "ticket_ref":   ticket_ref,
        "customer_ref": customer_ref,
        "subject":      subject[:200],
        "channel":      channel,
        "priority":     priority,
        "status":       "open",
        "message":      message,
        "created_at":   now_utc.isoformat(),
        "sla_deadline": sla_deadline.isoformat(),
        "updated_at":   now_utc.isoformat(),
        "escalated":    False,
        "notes":        [],
    }
    _TICKET_STORE[ticket_ref] = ticket

    logger.info(
        "_impl_create_ticket | ticket_ref=%s | sla=%dh | deadline=%s",
        ticket_ref, sla_hours, sla_deadline.isoformat(),
    )
    return {
        "ticket_ref":   ticket_ref,
        "created_at":   now_utc.isoformat(),
        "sla_deadline": sla_deadline.isoformat(),
        "status":       "open",
        "priority":     priority,
        "channel":      channel,
    }


def _impl_escalate_to_human(
    ticket_ref: str,
    reason: str,
    priority: str,
    customer_ref: str,
    notes: str = "",
) -> dict[str, Any]:
    """
    Escalate a ticket to the appropriate specialist queue.

    Returns
    -------
    dict: escalated, queue, escalation_id, escalated_at, priority, reason
    """
    logger.debug(
        "_impl_escalate_to_human | ticket_ref=%s | reason=%s | priority=%s",
        ticket_ref, reason, priority,
    )

    reason_lower = reason.lower().replace(" ", "_")
    queue = _ESCALATION_QUEUES.get(reason_lower)

    if queue is None:
        for key, q in _ESCALATION_QUEUES.items():
            if key in reason_lower:
                queue = q
                break
        if queue is None:
            queue = "general-support"
            logger.warning(
                "_impl_escalate_to_human | unknown reason %r — routing to general-support",
                reason,
            )

    escalation_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc).isoformat()

    if ticket_ref in _TICKET_STORE:
        _TICKET_STORE[ticket_ref].update({
            "status":            "escalated",
            "escalated":         True,
            "escalation_reason": reason,
            "escalation_queue":  queue,
            "escalation_id":     escalation_id,
            "escalated_at":      now_utc,
            "priority":          priority,
            "updated_at":        now_utc,
        })
        if notes:
            _TICKET_STORE[ticket_ref]["notes"].append(
                {"actor": "ai_agent", "text": notes, "ts": now_utc}
            )

    logger.info(
        "_impl_escalate_to_human | ticket_ref=%s | queue=%s | id=%s",
        ticket_ref, queue, escalation_id,
    )
    return {
        "escalated":     True,
        "queue":         queue,
        "escalation_id": escalation_id,
        "escalated_at":  now_utc,
        "priority":      priority,
        "reason":        reason,
    }


def _impl_analyze_sentiment(text: str) -> dict[str, Any]:
    """
    Rule-based sentiment analysis: anger, frustration, urgency, profanity.

    Returns
    -------
    dict: anger, frustration, urgency, profanity, overall, score, tone_flags, caps_ratio
    """
    logger.debug("_impl_analyze_sentiment | text_len=%d", len(text))

    text_lower = text.lower()
    tone_flags: list[str] = []

    alpha_chars = [c for c in text if c.isalpha()]
    caps_ratio = (
        sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars)
        if alpha_chars else 0.0
    )
    if caps_ratio > 0.40 and len(alpha_chars) > 10:
        tone_flags.append("excessive_caps")

    exclamation_count = text.count("!")
    if exclamation_count >= 3:
        tone_flags.append("exclamation_overuse")

    def _count_matches(patterns: list[str]) -> int:
        return sum(1 for p in patterns if re.search(p, text_lower))

    anger_hits = _count_matches(_ANGER_PATTERNS)
    frustration_hits = _count_matches(_FRUSTRATION_PATTERNS)
    urgency_detected = bool(_count_matches(_URGENCY_PATTERNS))
    profanity_detected = bool(_count_matches(_PROFANITY_PATTERNS))

    if urgency_detected:
        tone_flags.append("urgency")
    if profanity_detected:
        tone_flags.append("profanity")

    anger_score = min(anger_hits * 0.18, 0.85)
    if caps_ratio > 0.30:
        anger_score = min(anger_score + 0.20, 1.0)
    if exclamation_count >= 3:
        anger_score = min(anger_score + 0.10, 1.0)
    if profanity_detected:
        anger_score = min(anger_score + 0.35, 1.0)
    anger_score = round(anger_score, 3)

    frustration_score = round(min(frustration_hits * 0.15, 1.0), 3)

    if anger_score >= 0.65 or profanity_detected:
        overall = "angry"
        tone_flags.append("anger")
    elif frustration_score >= 0.45 or anger_score >= 0.35:
        overall = "frustrated"
        tone_flags.append("frustration")
    elif any(
        w in text_lower
        for w in ("thank", "great", "love", "awesome", "amazing", "helpful", "excellent")
    ):
        overall = "positive"
        tone_flags.append("positive_signal")
    else:
        overall = "neutral"

    composite_score = round(
        min(
            anger_score * 0.6
            + frustration_score * 0.3
            + (0.1 if urgency_detected else 0.0),
            1.0,
        ),
        3,
    )

    result = {
        "anger":       anger_score,
        "frustration": frustration_score,
        "urgency":     urgency_detected,
        "profanity":   profanity_detected,
        "overall":     overall,
        "score":       composite_score,
        "tone_flags":  list(set(tone_flags)),
        "caps_ratio":  round(caps_ratio, 3),
    }
    logger.info(
        "_impl_analyze_sentiment | overall=%s | anger=%.2f | frustration=%.2f | urgency=%s",
        result["overall"], result["anger"], result["frustration"], result["urgency"],
    )
    return result


def _impl_update_ticket_status(
    ticket_ref: str,
    new_status: str,
    notes: str = "",
) -> dict[str, Any]:
    """
    Update ticket status in the in-memory store.

    Returns
    -------
    dict: updated, ticket_ref, new_status, updated_at, message
    """
    _VALID_STATUSES = {
        "open", "in_progress", "waiting_customer", "escalated", "resolved",
    }
    logger.debug(
        "_impl_update_ticket_status | ticket_ref=%s | new_status=%s", ticket_ref, new_status
    )

    now_utc = datetime.now(timezone.utc).isoformat()

    if new_status not in _VALID_STATUSES:
        logger.warning(
            "_impl_update_ticket_status | invalid status %r for ticket %s",
            new_status, ticket_ref,
        )
        return {
            "updated":    False,
            "ticket_ref": ticket_ref,
            "new_status": new_status,
            "updated_at": now_utc,
            "message":    f"Invalid status '{new_status}'. Must be one of {sorted(_VALID_STATUSES)}.",
        }

    if ticket_ref not in _TICKET_STORE:
        logger.warning("_impl_update_ticket_status | ticket_ref=%s not found", ticket_ref)
        return {
            "updated":    False,
            "ticket_ref": ticket_ref,
            "new_status": new_status,
            "updated_at": now_utc,
            "message":    f"Ticket {ticket_ref} not found.",
        }

    _TICKET_STORE[ticket_ref]["status"] = new_status
    _TICKET_STORE[ticket_ref]["updated_at"] = now_utc
    if notes:
        _TICKET_STORE[ticket_ref]["notes"].append(
            {"actor": "ai_agent", "text": notes, "ts": now_utc}
        )

    logger.info("_impl_update_ticket_status | ticket_ref=%s | new_status=%s", ticket_ref, new_status)
    return {
        "updated":    True,
        "ticket_ref": ticket_ref,
        "new_status": new_status,
        "updated_at": now_utc,
        "message":    f"Ticket {ticket_ref} status updated to '{new_status}'.",
    }


# ===========================================================================
# SDK-wrapped public tool objects
# When openai-agents IS installed these become FunctionTool objects for the
# SDK Runner.  When it is NOT installed they remain plain callables.
# ===========================================================================

search_knowledge_base = _sdk_function_tool(_impl_search_knowledge_base)
get_customer_history  = _sdk_function_tool(_impl_get_customer_history)
create_ticket         = _sdk_function_tool(_impl_create_ticket)
escalate_to_human     = _sdk_function_tool(_impl_escalate_to_human)
analyze_sentiment     = _sdk_function_tool(_impl_analyze_sentiment)
update_ticket_status  = _sdk_function_tool(_impl_update_ticket_status)

# List of SDK-wrapped tools for registration with Agent(tools=ALL_TOOLS)
ALL_TOOLS: list[Any] = [
    search_knowledge_base,
    get_customer_history,
    create_ticket,
    escalate_to_human,
    analyze_sentiment,
    update_ticket_status,
]
