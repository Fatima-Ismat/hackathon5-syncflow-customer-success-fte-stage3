"""
Knowledge Service – Stage 2
NovaSync Technologies / SyncFlow Customer Success Digital FTE

Extends Stage 1 keyword-based KB search with:
  - Multi-factor scoring (keyword overlap + tag match + phrase match + recency)
  - Channel-aware answer selection (short form for WhatsApp, full form for email)
  - Solution suggestion with ranked alternatives
  - Usage tracking for KB analytics

Functions:
    search_docs()        Primary search: returns ranked KB results
    suggest_solution()   Higher-level wrapper: best answer + alternatives
    rank_answers()       Re-rank a list of results by additional signals

Stage 3 upgrade: replace keyword scoring with vector embeddings + Claude semantic search.
"""

import re
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Knowledge Base Entries (extends Stage 1 KB)
# ---------------------------------------------------------------------------

KB_ENTRIES: dict[str, dict] = {
    "password_reset": {
        "section_id": "password_reset",
        "title":      "Password & Security → Password Reset",
        "keywords":   {"password", "reset", "forgot", "login", "locked", "lockout"},
        "tags":       ["security", "authentication", "account"],
        "answer": (
            "To reset your password:\n"
            "1. Go to app.syncflow.io/login\n"
            "2. Click 'Forgot Password'\n"
            "3. Enter your email address\n"
            "4. Check your inbox — the reset link is valid for 60 minutes\n"
            "5. Create a new password (min 12 characters, uppercase + number + symbol)\n\n"
            "Note: After reset, all active sessions are terminated."
        ),
        "whatsapp_answer": (
            "To reset your password: app.syncflow.io/login → Forgot Password → enter email. "
            "Reset link valid 60 mins. New password needs 12+ chars."
        ),
        "times_retrieved": 0,
        "times_led_to_resolve": 0,
    },
    "two_factor_auth": {
        "section_id": "two_factor_auth",
        "title":      "Password & Security → Two-Factor Authentication",
        "keywords":   {"2fa", "two-factor", "authenticator", "otp", "verification", "invalid", "code"},
        "tags":       ["security", "authentication"],
        "answer": (
            "If your 2FA code shows as invalid:\n"
            "1. Ensure your phone's time is synced (authenticator apps are time-sensitive)\n"
            "2. Use a fresh code — don't use one older than 30 seconds\n"
            "3. Supported apps: Google Authenticator, Authy, 1Password, Microsoft Authenticator\n\n"
            "To enable 2FA: Settings → Security → Two-Factor Authentication → Enable"
        ),
        "whatsapp_answer": (
            "2FA invalid code: sync your phone's time, use a fresh code (<30s). "
            "Enable at: Settings → Security → Two-Factor Authentication."
        ),
        "times_retrieved": 0,
        "times_led_to_resolve": 0,
    },
    "api_errors": {
        "section_id": "api_errors",
        "title":      "API Usage → API Keys & Error Codes",
        "keywords":   {"api", "key", "401", "403", "429", "rate", "limit", "unauthorized", "forbidden", "error"},
        "tags":       ["api", "developer", "errors"],
        "answer": (
            "Common API errors:\n"
            "• 401 Unauthorized: Your API key is invalid or expired. Regenerate at Settings → Developer → API Keys\n"
            "• 403 Forbidden: Key lacks permission for this action. Check key scope\n"
            "• 429 Too Many Requests: Rate limit hit. Wait for X-RateLimit-Reset or upgrade plan\n"
            "• 404 Not Found: Verify resource ID in your request\n"
            "• 500 Server Error: Contact support with the request ID from response headers\n\n"
            "Rate limits by plan:\n"
            "  Starter: 60 req/min | Growth: 300 req/min | Business: 1,000 req/min"
        ),
        "whatsapp_answer": (
            "API errors: 401=expired key (regenerate in Settings→Developer), "
            "403=wrong permissions, 429=rate limit hit. "
            "Limits: Starter 60/min, Growth 300/min, Business 1000/min."
        ),
        "times_retrieved": 0,
        "times_led_to_resolve": 0,
    },
    "billing": {
        "section_id": "billing",
        "title":      "Billing & Subscriptions",
        "keywords":   {"billing", "invoice", "charge", "payment", "subscription", "cost", "price", "plan", "upgrade", "downgrade", "proration"},
        "tags":       ["billing", "payments", "account"],
        "answer": (
            "Billing details:\n"
            "• Invoices generated 1st of each month (Settings → Billing → Invoice History)\n"
            "• Upgrading: takes effect immediately with prorated charge for remaining cycle\n"
            "• Downgrading: takes effect at the start of the next billing cycle\n"
            "• Refund policy:\n"
            "  - Annual plans: pro-rated refund within 30 days of charge\n"
            "  - Monthly plans: no refund for the current billing period\n\n"
            "For billing questions: billing@novasynctechnologies.com"
        ),
        "whatsapp_answer": (
            "Invoices on 1st of month (Settings→Billing). Upgrades are immediate + prorated. "
            "Downgrades start next cycle. Refunds: annual plans within 30 days only."
        ),
        "times_retrieved": 0,
        "times_led_to_resolve": 0,
    },
    "integrations": {
        "section_id": "integrations",
        "title":      "Integrations → Connecting an Integration",
        "keywords":   {"salesforce", "hubspot", "slack", "google", "sheets", "oauth", "connect", "integration", "authorize"},
        "tags":       ["integrations", "oauth", "third-party"],
        "answer": (
            "To connect an integration:\n"
            "1. Dashboard → Integrations → Browse\n"
            "2. Search for the app\n"
            "3. Click Connect → Authorize via OAuth\n"
            "4. Configure field mapping and sync settings\n"
            "5. Test the connection\n\n"
            "If OAuth fails with 'redirect_uri_mismatch': clear browser cookies and try again. "
            "If the error persists, try a different browser."
        ),
        "whatsapp_answer": (
            "Connect integrations: Dashboard → Integrations → Browse → Connect → OAuth. "
            "OAuth error? Clear cookies or try different browser."
        ),
        "times_retrieved": 0,
        "times_led_to_resolve": 0,
    },
    "oauth_token_expiry": {
        "section_id": "oauth_token_expiry",
        "title":      "Integrations → OAuth Token Expiry",
        "keywords":   {"oauth", "token", "expired", "reconnect", "session", "invalid_session", "reconnecting"},
        "tags":       ["integrations", "oauth"],
        "answer": (
            "OAuth tokens expire periodically for security.\n\n"
            "When expired: you'll see a 'Reconnect Required' banner on the affected integration. "
            "Affected workflows will fail and generate error logs.\n\n"
            "Fix: Integrations → [App] → Reconnect → Re-authorize. "
            "Your workflows will resume automatically."
        ),
        "whatsapp_answer": (
            "OAuth expired? Integrations → [App] → Reconnect → Re-authorize. "
            "Workflows auto-resume after reconnection."
        ),
        "times_retrieved": 0,
        "times_led_to_resolve": 0,
    },
    "workflow_trigger": {
        "section_id": "workflow_trigger",
        "title":      "Troubleshooting → Workflow Not Triggering",
        "keywords":   {"workflow", "trigger", "firing", "stopped", "scheduled", "paused", "automation", "not working"},
        "tags":       ["workflows", "troubleshooting", "automation"],
        "answer": (
            "If your workflow isn't triggering:\n"
            "1. Confirm workflow status is Active (not Paused or Draft)\n"
            "2. Verify trigger conditions are correctly configured\n"
            "3. For webhook triggers: check if the source app's webhook is still registered\n"
            "4. For scheduled triggers: confirm the timezone setting is correct\n"
            "5. Check your plan's monthly automation run limit hasn't been reached\n\n"
            "View run history: Workflows → [Workflow Name] → Run History"
        ),
        "whatsapp_answer": (
            "Workflow not triggering: check status is Active, verify trigger settings. "
            "Webhook trigger? Re-check registration. "
            "See: Workflows → [Name] → Run History."
        ),
        "times_retrieved": 0,
        "times_led_to_resolve": 0,
    },
    "webhooks": {
        "section_id": "webhooks",
        "title":      "API Usage → Webhooks",
        "keywords":   {"webhook", "duplicate", "firing", "twice", "multiple", "retry", "event", "idempotent"},
        "tags":       ["api", "webhooks", "developer"],
        "answer": (
            "Duplicate webhook events occur when:\n"
            "• Your endpoint didn't return 200 OK within 5 seconds, triggering a retry\n"
            "• SyncFlow retry policy: 1m, 5m, 30m, 2h, 12h\n\n"
            "Solution:\n"
            "1. Ensure your endpoint responds with 200 within 5 seconds\n"
            "2. Implement idempotency using the event ID in X-SyncFlow-Event-ID header "
            "to deduplicate on your end"
        ),
        "whatsapp_answer": (
            "Duplicate webhooks? Your endpoint must return 200 within 5s. "
            "Use X-SyncFlow-Event-ID header to deduplicate."
        ),
        "times_retrieved": 0,
        "times_led_to_resolve": 0,
    },
    "sso": {
        "section_id": "sso",
        "title":      "Password & Security → Single Sign-On",
        "keywords":   {"sso", "saml", "okta", "azure", "google workspace", "single sign", "active directory"},
        "tags":       ["security", "enterprise", "authentication"],
        "answer": (
            "SSO is available on Business and Enterprise plans.\n"
            "Supported providers: Okta, Azure AD, Google Workspace, OneLogin\n\n"
            "Common SSO issues:\n"
            "• 'SSO not configured': Enable at Settings → Security → SSO\n"
            "• Email domain mismatch: Confirm your email matches the configured domain\n"
            "• Redirect loop: Clear cookies and try incognito mode\n\n"
            "SSO requires Admin access to configure. Contact your IT administrator."
        ),
        "whatsapp_answer": (
            "SSO available on Business/Enterprise. Providers: Okta, Azure AD, Google Workspace. "
            "Domain mismatch error? Check Settings→Security→SSO config."
        ),
        "times_retrieved": 0,
        "times_led_to_resolve": 0,
    },
    "data_export": {
        "section_id": "data_export",
        "title":      "Data & Privacy → Exporting Your Data",
        "keywords":   {"export", "data", "download", "cancel", "cancellation", "delete", "backup", "retention"},
        "tags":       ["data", "privacy", "account"],
        "answer": (
            "To export your account data:\n"
            "Settings → Data → Export Account Data\n\n"
            "Export includes: workflows, run history, team settings, integration configs, custom fields.\n"
            "Processing time: up to 2 hours for large accounts.\n\n"
            "After cancellation: data retained for 90 days before permanent deletion."
        ),
        "whatsapp_answer": (
            "Data export: Settings → Data → Export Account Data. Up to 2 hours. "
            "After cancellation, data kept 90 days."
        ),
        "times_retrieved": 0,
        "times_led_to_resolve": 0,
    },
    "team_management": {
        "section_id": "team_management",
        "title":      "Account Management → Managing Team Members",
        "keywords":   {"seat", "member", "invite", "team", "viewer", "admin", "role", "permission", "user"},
        "tags":       ["account", "team", "permissions"],
        "answer": (
            "Team roles:\n"
            "• Admin: Full account access including billing\n"
            "• Member: Access to assigned workspaces only\n"
            "• Viewer: Read-only access to shared dashboards\n\n"
            "To invite: Settings → Team → Invite Members → Enter email → Select role → Send Invite\n"
            "Invites expire after 7 days.\n\n"
            "Seat limits: Starter 5 | Growth 25 | Business 100 | Enterprise unlimited"
        ),
        "whatsapp_answer": (
            "Invite team: Settings→Team→Invite Members. Roles: Admin, Member, Viewer. "
            "Invites expire in 7 days. Seats: Starter 5, Growth 25, Business 100."
        ),
        "times_retrieved": 0,
        "times_led_to_resolve": 0,
    },
    "workspaces": {
        "section_id": "workspaces",
        "title":      "Account Management → Workspaces",
        "keywords":   {"workspace", "department", "project", "client", "isolated", "environment"},
        "tags":       ["account", "organization"],
        "answer": (
            "Workspaces are isolated environments within your account.\n\n"
            "Limits: Starter 3 | Growth 10 | Business/Enterprise unlimited\n\n"
            "To create: Dashboard → New Workspace → Name → Set permissions"
        ),
        "whatsapp_answer": (
            "Create workspace: Dashboard → New Workspace. "
            "Limits: Starter 3, Growth 10, Business/Enterprise unlimited."
        ),
        "times_retrieved": 0,
        "times_led_to_resolve": 0,
    },
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def search_docs(
    query: str,
    channel: str = "email",
    max_results: int = 3,
) -> dict:
    """
    Search the knowledge base using multi-factor keyword scoring.

    Scoring factors:
      1. Keyword token overlap (primary signal)
      2. Exact keyword phrase matches (boost: +0.15 per match)
      3. Tag relevance (boost: +0.10 if query word matches a tag)

    Args:
        query:       Customer's question or issue description.
        channel:     "email" | "whatsapp" | "web_form" — selects answer variant.
        max_results: Maximum results to return.

    Returns:
        dict with:
          - results:       list of scored KB entries (sorted by confidence desc)
          - answer_found:  bool — True if best result confidence >= 0.30
          - best_answer:   str — channel-appropriate answer text
          - confidence:    float — confidence of the top result
          - section:       str — title of the top matching section
          - search_ts:     str — ISO 8601 timestamp
    """
    if not query or not query.strip():
        return _no_results(query)

    query_lower = query.lower()
    query_tokens = set(re.findall(r'\b\w+\b', query_lower))

    scored = []
    for entry in KB_ENTRIES.values():
        score = _score_entry(entry, query_lower, query_tokens)
        if score > 0.05:
            scored.append((score, entry))

    if not scored:
        return _no_results(query)

    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:max_results]

    best_score, best_entry = top[0]
    answer = _pick_answer(best_entry, channel)

    # Track usage
    best_entry["times_retrieved"] += 1

    results = [
        {
            "section_id":       e["section_id"],
            "title":            e["title"],
            "confidence":       round(s, 2),
            "answer":           _pick_answer(e, channel),
            "tags":             e["tags"],
        }
        for s, e in top
    ]

    return {
        "results":      results,
        "answer_found": best_score >= 0.30,
        "best_answer":  answer,
        "confidence":   round(best_score, 2),
        "section":      best_entry["title"],
        "section_id":   best_entry["section_id"],
        "query":        query,
        "search_ts":    datetime.utcnow().isoformat(),
    }


def suggest_solution(
    query: str,
    channel: str = "email",
    customer_plan: str = "starter",
) -> dict:
    """
    High-level solution suggestion combining KB search with plan-aware context.

    Adds plan-specific guidance when relevant (e.g., rate limit suggestions).

    Args:
        query:          Customer's question.
        channel:        Delivery channel.
        customer_plan:  Used to tailor plan-specific content (e.g., rate limits).

    Returns:
        dict with:
          - suggested_answer:  str — best answer text, possibly with plan context
          - confidence:        float
          - section:           str
          - alternatives:      list — up to 2 alternative KB results
          - answer_found:      bool
    """
    result = search_docs(query, channel=channel, max_results=3)

    suggested = result.get("best_answer", "")

    # Add plan-specific context for rate limit queries
    if result.get("section_id") == "api_errors" and "429" in query:
        plan_limits = {
            "starter":    "60 requests/minute",
            "growth":     "300 requests/minute",
            "business":   "1,000 requests/minute",
            "enterprise": "custom limits",
        }
        limit = plan_limits.get(customer_plan, "see your plan details")
        suggested += f"\n\nYour current plan ({customer_plan}) allows {limit}."

    alternatives = []
    all_results = result.get("results", [])
    if len(all_results) > 1:
        alternatives = all_results[1:]  # everything except the best

    return {
        "suggested_answer": suggested,
        "confidence":       result.get("confidence", 0.0),
        "section":          result.get("section"),
        "section_id":       result.get("section_id"),
        "answer_found":     result.get("answer_found", False),
        "alternatives":     alternatives,
        "query":            query,
    }


def rank_answers(
    results: list[dict],
    prefer_short: bool = False,
) -> list[dict]:
    """
    Re-rank a list of search results by secondary signals.

    Secondary signals applied:
      - Resolution rate: KB entries that historically resolved tickets rank higher
      - Answer length penalty when prefer_short=True (WhatsApp channel)

    Args:
        results:       List of result dicts from search_docs().
        prefer_short:  If True, penalize long answers (for WhatsApp).

    Returns:
        Re-ranked list of results.
    """
    def _rank_score(result: dict) -> float:
        base = result.get("confidence", 0.0)
        section_id = result.get("section_id")
        entry = KB_ENTRIES.get(section_id, {})

        # Boost from historical resolution rate
        retrieved = entry.get("times_retrieved", 0)
        resolved  = entry.get("times_led_to_resolve", 0)
        if retrieved > 0:
            rate = resolved / retrieved
            base += rate * 0.10

        # Penalize long answers for WhatsApp
        if prefer_short:
            answer_len = len(result.get("answer", "").split())
            if answer_len > 60:
                base -= 0.05
            if answer_len > 100:
                base -= 0.05

        return base

    return sorted(results, key=_rank_score, reverse=True)


def mark_resolved(section_id: str) -> None:
    """
    Mark that a KB entry contributed to a ticket resolution.
    Called by the ticket service when a ticket is resolved.
    """
    entry = KB_ENTRIES.get(section_id)
    if entry:
        entry["times_led_to_resolve"] += 1
        retrieved = entry.get("times_retrieved", 1)
        entry["resolution_rate"] = round(
            entry["times_led_to_resolve"] / max(retrieved, 1), 3
        )


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _score_entry(entry: dict, query_lower: str, query_tokens: set) -> float:
    """Compute a confidence score for a single KB entry against a query."""
    keywords = entry["keywords"]
    overlap  = query_tokens & keywords

    if not overlap:
        return 0.0

    score = len(overlap) / max(len(keywords), 1)

    # Phrase match boost
    for kw in keywords:
        if kw in query_lower:
            score += 0.15

    # Tag match boost
    for tag in entry.get("tags", []):
        if tag.lower() in query_lower:
            score += 0.10

    return min(score, 1.0)


def _pick_answer(entry: dict, channel: str) -> str:
    """Select channel-appropriate answer variant."""
    if channel == "whatsapp" and entry.get("whatsapp_answer"):
        return entry["whatsapp_answer"]
    return entry.get("answer", "")


def _no_results(query: str) -> dict:
    return {
        "results":      [],
        "answer_found": False,
        "best_answer":  "",
        "confidence":   0.10,
        "section":      None,
        "section_id":   None,
        "query":        query,
        "search_ts":    datetime.utcnow().isoformat(),
    }
