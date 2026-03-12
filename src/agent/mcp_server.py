"""
MCP Server – Customer Success Tools
NovaSync Technologies / SyncFlow Support

This module defines the Model Context Protocol (MCP) server that exposes
support tools to the Customer Success AI Agent.

Each tool is a function the agent can call during conversation processing
to look up data, create records, or trigger actions in backend systems.

Stage 1 Note: All tool implementations use in-memory mock data.
In Stage 2, these will call real APIs (CRM, ticketing system, email gateway).

Tools exposed:
  - search_knowledge_base(query)
  - create_ticket(customer_id, issue, priority, channel)
  - get_customer_history(customer_id)
  - send_response(ticket_id, message, channel)
  - escalate_to_human(ticket_id, reason)
"""

import json
import random
import re
from datetime import datetime, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# Mock Data Stores (replaces real database/API in Stage 1)
# ---------------------------------------------------------------------------

_TICKET_STORE: dict = {}   # ticket_id -> ticket dict
_RESPONSE_LOG: list = []   # log of all sent responses
_ESCALATION_LOG: list = [] # log of all escalations

_MOCK_CUSTOMER_HISTORY = {
    "C-1042": {
        "name": "Marcus Chen",
        "email": "marcus.chen@acme.io",
        "plan": "growth",
        "account_created": "2024-03-15",
        "total_tickets": 3,
        "recent_tickets": [
            {"ticket_id": "TKT-20240901-2211", "topic": "billing_question", "status": "resolved", "date": "2024-09-01"},
            {"ticket_id": "TKT-20241112-3301", "topic": "integration_oauth_error", "status": "resolved", "date": "2024-11-12"},
        ],
        "open_tickets": 0,
        "last_contact": "2024-11-12",
        "csat_average": 4.6,
        "is_vip": False,
        "account_health": "healthy",
        "mrr": 99.0,
    },
    "C-2817": {
        "name": "Priya Nair",
        "email": "priya.nair@startup.io",
        "plan": "starter",
        "account_created": "2025-01-10",
        "total_tickets": 1,
        "recent_tickets": [],
        "open_tickets": 1,
        "last_contact": "2026-03-09",
        "csat_average": None,
        "is_vip": False,
        "account_health": "healthy",
        "mrr": 29.0,
    },
    "C-3301": {
        "name": "James Whitfield",
        "email": "j.whitfield@techbridge.com",
        "plan": "business",
        "account_created": "2023-07-22",
        "total_tickets": 8,
        "recent_tickets": [
            {"ticket_id": "TKT-20260101-0091", "topic": "billing_upgrade_confusion", "status": "resolved", "date": "2026-01-01"},
        ],
        "open_tickets": 0,
        "last_contact": "2026-01-01",
        "csat_average": 4.2,
        "is_vip": False,
        "account_health": "healthy",
        "mrr": 299.0,
    },
    "C-4451": {
        "name": "Sofia Reyes",
        "email": "s.reyes@marketingco.com",
        "plan": "growth",
        "account_created": "2025-06-01",
        "total_tickets": 5,
        "recent_tickets": [
            {"ticket_id": "TKT-20260201-1122", "topic": "api_rate_limit", "status": "resolved", "date": "2026-02-01"},
            {"ticket_id": "TKT-20260215-2233", "topic": "api_rate_limit", "status": "resolved", "date": "2026-02-15"},
        ],
        "open_tickets": 0,
        "last_contact": "2026-02-15",
        "csat_average": 3.8,
        "is_vip": False,
        "account_health": "at_risk",
        "mrr": 99.0,
    },
    "C-6229": {
        "name": "Lena Hoffmann",
        "email": "l.hoffmann@enterprise-solutions.de",
        "plan": "business",
        "account_created": "2022-11-05",
        "total_tickets": 12,
        "recent_tickets": [],
        "open_tickets": 0,
        "last_contact": "2026-01-20",
        "csat_average": 4.9,
        "is_vip": True,
        "account_health": "healthy",
        "mrr": 299.0,
    },
}

# Knowledge base sections (simplified for MCP tool)
_KB_SECTIONS = {
    "password_reset": {
        "title": "Password & Security -> Password Reset",
        "content": "To reset your password: go to app.syncflow.io/login -> Forgot Password -> enter email -> check inbox (link valid 60 minutes) -> create new password (12+ chars, uppercase + number + symbol). Note: resets all active sessions.",
        "tags": ["password", "reset", "forgot", "locked out", "login"],
    },
    "api_rate_limits": {
        "title": "API Usage -> Rate Limits",
        "content": "Rate limits: Starter 60 req/min / 10K/day | Growth 300 req/min / 100K/day | Business 1,000 req/min / 1M/day. On 429 error, check X-RateLimit-Reset header and wait. Upgrade plan for higher limits.",
        "tags": ["api", "rate limit", "429", "too many requests"],
    },
    "api_errors": {
        "title": "API Usage -> Error Codes",
        "content": "401 = invalid/expired key (regenerate at Settings -> Developer -> API Keys). 403 = insufficient permissions (check key scope). 404 = resource not found (verify ID). 500 = server error (contact support with request ID). 503 = outage (check status.syncflow.io).",
        "tags": ["api", "401", "403", "404", "500", "error"],
    },
    "billing": {
        "title": "Billing & Subscriptions",
        "content": "Invoices on 1st of month. Upgrades: immediate + prorated charge. Downgrades: next cycle. Refunds: annual plans within 30 days, monthly plans no current-period refund. For refunds: billing@novasynctechnologies.com. Payment: Visa, MC, Amex, PayPal, ACH (Enterprise).",
        "tags": ["billing", "invoice", "charge", "refund", "payment", "upgrade", "downgrade"],
    },
    "integrations": {
        "title": "Integrations -> Setup & Troubleshooting",
        "content": "Connect: Dashboard -> Integrations -> Browse -> Connect -> OAuth. If OAuth fails: clear cookies, try different browser. For session-expired errors (INVALID_SESSION_ID): Integrations -> [App] -> Reconnect -> Re-authorize. Disconnecting pauses workflows using that integration.",
        "tags": ["integration", "salesforce", "slack", "oauth", "connect", "reconnect", "session"],
    },
    "sso": {
        "title": "Password & Security -> SSO",
        "content": "SSO available on Business and Enterprise plans. Providers: Okta, Azure AD, Google Workspace, OneLogin. Requires Admin access and SAML 2.0 configuration. Common issue: domain mismatch — confirm email domain matches SSO config.",
        "tags": ["sso", "saml", "okta", "azure", "single sign-on"],
    },
    "workflows": {
        "title": "Workflows & Automations",
        "content": "If workflow not triggering: check status is Active, verify trigger conditions, check webhook registration, confirm timezone for scheduled triggers. Limits: Starter 10 workflows/500 runs/mo | Growth 50/5K | Business unlimited.",
        "tags": ["workflow", "automation", "trigger", "schedule", "not working"],
    },
    "data_export": {
        "title": "Data & Privacy -> Exporting Your Data",
        "content": "Export: Settings -> Data -> Export Account Data. Includes workflows, run history, team settings, integration configs. Processing: up to 2 hours. Post-cancellation data retained 90 days then deleted.",
        "tags": ["export", "data", "download", "cancel", "backup"],
    },
    "team_management": {
        "title": "Account Management -> Team Members",
        "content": "Invite: Settings -> Team -> Invite Members -> email + role (Admin/Member/Viewer) -> Send (expires 7 days). Remove: Settings -> Team -> Remove (immediate). Seats: Starter 5, Growth 25, Business 100, Enterprise unlimited.",
        "tags": ["team", "invite", "member", "admin", "viewer", "seat", "role"],
    },
    "2fa": {
        "title": "Password & Security -> Two-Factor Authentication",
        "content": "Enable 2FA: Settings -> Security -> Two-Factor Authentication -> choose Authenticator App or SMS -> scan QR code -> enter 6-digit code -> save backup codes. If 'invalid code': sync device time, use fresh code (<30s old). Supported apps: Google Authenticator, Authy, 1Password, Microsoft Authenticator.",
        "tags": ["2fa", "two factor", "authenticator", "otp", "invalid code", "security"],
    },
}


# ---------------------------------------------------------------------------
# MCP Tool: search_knowledge_base
# ---------------------------------------------------------------------------

def search_knowledge_base(query: str, max_results: int = 3) -> dict:
    """
    MCP Tool: Search the SyncFlow knowledge base for relevant support content.

    This tool allows the agent to look up product documentation, troubleshooting
    guides, and policy information in response to a customer query.

    Args:
        query (str):
            The customer's question or issue description. Can be a full
            sentence or keyword phrase. Example: "how do I reset my password"
        max_results (int):
            Maximum number of matching sections to return (default: 3).
            Higher values provide more context but may increase noise.

    Returns:
        dict:
            {
                "results": [
                    {
                        "section_id": str,
                        "title": str,
                        "content": str,
                        "relevance_score": float (0.0–1.0),
                        "tags": list[str]
                    }
                ],
                "total_found": int,
                "query": str,
                "search_timestamp": str (ISO 8601)
            }

    Example:
        >>> result = search_knowledge_base("getting 429 rate limit on API")
        >>> result["results"][0]["title"]
        "API Usage -> Rate Limits"
    """
    query_lower = query.lower()
    query_tokens = set(re.findall(r'\b\w+\b', query_lower))
    scored_results = []

    for section_id, section in _KB_SECTIONS.items():
        # Keyword overlap scoring
        tag_tokens = set(" ".join(section["tags"]).lower().split())
        overlap = query_tokens & tag_tokens
        score = len(overlap) / max(len(tag_tokens), 1) if tag_tokens else 0

        # Boost for direct tag matches
        for tag in section["tags"]:
            if tag in query_lower:
                score += 0.20

        score = min(round(score, 2), 1.0)

        if score > 0.05:
            scored_results.append({
                "section_id": section_id,
                "title": section["title"],
                "content": section["content"],
                "relevance_score": score,
                "tags": section["tags"],
            })

    # Sort by relevance
    scored_results.sort(key=lambda x: x["relevance_score"], reverse=True)
    top_results = scored_results[:max_results]

    return {
        "results": top_results,
        "total_found": len(top_results),
        "query": query,
        "search_timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# MCP Tool: create_ticket
# ---------------------------------------------------------------------------

def create_ticket(
    customer_id: str,
    issue: str,
    priority: str,
    channel: str,
    topic: Optional[str] = None,
    sentiment_score: Optional[float] = None,
) -> dict:
    """
    MCP Tool: Create a new support ticket in the ticketing system.

    This tool is called when a new customer interaction is received and
    needs to be tracked. It generates a unique ticket ID and stores all
    relevant metadata for the conversation.

    Args:
        customer_id (str):
            The customer's unique identifier (e.g., "C-1042").
        issue (str):
            A brief description of the customer's issue.
            Example: "Customer cannot log in after password reset"
        priority (str):
            Ticket priority level: "critical" | "high" | "medium" | "low"
        channel (str):
            The channel through which the request arrived:
            "email" | "whatsapp" | "web_form"
        topic (str, optional):
            Classified issue topic (e.g., "password_reset", "billing_question").
        sentiment_score (float, optional):
            Detected anger/frustration score from sentiment analysis (0.0–1.0).

    Returns:
        dict:
            {
                "ticket_id": str,
                "customer_id": str,
                "issue": str,
                "priority": str,
                "channel": str,
                "topic": str | None,
                "status": "open",
                "created_at": str (ISO 8601),
                "sla_deadline": str (ISO 8601),
                "assigned_to": "ai_agent" | "human_queue"
            }

    Example:
        >>> ticket = create_ticket("C-1042", "API rate limit exceeded", "medium", "email")
        >>> ticket["ticket_id"]
        "TKT-20260310-4821"
    """
    valid_priorities = {"critical", "high", "medium", "low"}
    valid_channels = {"email", "whatsapp", "web_form"}

    if priority not in valid_priorities:
        priority = "medium"
    if channel not in valid_channels:
        channel = "web_form"

    ticket_id = f"TKT-{datetime.utcnow().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"

    # Determine SLA deadline based on customer plan
    customer_data = _MOCK_CUSTOMER_HISTORY.get(customer_id, {})
    plan = customer_data.get("plan", "starter")
    sla_hours = {"starter": 24, "growth": 8, "business": 2, "enterprise": 1}.get(plan, 24)
    if priority == "critical":
        sla_hours = min(sla_hours, 1)
    elif priority == "high":
        sla_hours = min(sla_hours, 4)

    sla_deadline = (datetime.utcnow() + timedelta(hours=sla_hours)).isoformat()

    ticket = {
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "customer_name": customer_data.get("name", "Unknown"),
        "issue": issue,
        "priority": priority,
        "channel": channel,
        "topic": topic,
        "sentiment_score": sentiment_score,
        "status": "open",
        "created_at": datetime.utcnow().isoformat(),
        "sla_deadline": sla_deadline,
        "assigned_to": "ai_agent",
        "messages": [],
    }

    _TICKET_STORE[ticket_id] = ticket

    return {
        "ticket_id": ticket_id,
        "customer_id": customer_id,
        "issue": issue,
        "priority": priority,
        "channel": channel,
        "topic": topic,
        "status": "open",
        "created_at": ticket["created_at"],
        "sla_deadline": sla_deadline,
        "assigned_to": "ai_agent",
    }


# ---------------------------------------------------------------------------
# MCP Tool: get_customer_history
# ---------------------------------------------------------------------------

def get_customer_history(customer_id: str, limit: int = 5) -> dict:
    """
    MCP Tool: Retrieve a customer's support history and account details.

    Provides the agent with context about who the customer is, what plan
    they're on, their recent ticket history, CSAT scores, and account health.
    This information is used to personalize responses and adjust escalation
    thresholds appropriately.

    Args:
        customer_id (str):
            The customer's unique identifier (e.g., "C-1042").
        limit (int):
            Maximum number of recent tickets to return (default: 5).

    Returns:
        dict:
            {
                "found": bool,
                "customer_id": str,
                "name": str,
                "email": str,
                "plan": str,
                "account_created": str,
                "total_tickets": int,
                "recent_tickets": list[dict],
                "open_tickets": int,
                "last_contact": str,
                "csat_average": float | None,
                "is_vip": bool,
                "account_health": str,
                "mrr": float,
                "retrieved_at": str (ISO 8601)
            }

    Example:
        >>> history = get_customer_history("C-1042")
        >>> history["plan"]
        "growth"
        >>> history["account_health"]
        "healthy"
    """
    customer = _MOCK_CUSTOMER_HISTORY.get(customer_id)

    if not customer:
        return {
            "found": False,
            "customer_id": customer_id,
            "name": None,
            "email": None,
            "plan": "unknown",
            "account_created": None,
            "total_tickets": 0,
            "recent_tickets": [],
            "open_tickets": 0,
            "last_contact": None,
            "csat_average": None,
            "is_vip": False,
            "account_health": "unknown",
            "mrr": 0.0,
            "retrieved_at": datetime.utcnow().isoformat(),
        }

    recent = customer.get("recent_tickets", [])[:limit]

    return {
        "found": True,
        "customer_id": customer_id,
        "name": customer["name"],
        "email": customer["email"],
        "plan": customer["plan"],
        "account_created": customer["account_created"],
        "total_tickets": customer["total_tickets"],
        "recent_tickets": recent,
        "open_tickets": customer["open_tickets"],
        "last_contact": customer["last_contact"],
        "csat_average": customer["csat_average"],
        "is_vip": customer["is_vip"],
        "account_health": customer["account_health"],
        "mrr": customer["mrr"],
        "retrieved_at": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# MCP Tool: send_response
# ---------------------------------------------------------------------------

def send_response(ticket_id: str, message: str, channel: str) -> dict:
    """
    MCP Tool: Send a formatted response to the customer via the appropriate channel.

    This tool dispatches the agent's response through the correct channel
    adapter (email gateway, WhatsApp Business API, or web form response API).
    It also logs the response to the ticket and response store.

    Args:
        ticket_id (str):
            The ticket ID this response is associated with (e.g., "TKT-20260310-4821").
        message (str):
            The formatted message content to send to the customer.
            Must already be formatted for the target channel.
        channel (str):
            The delivery channel: "email" | "whatsapp" | "web_form"

    Returns:
        dict:
            {
                "success": bool,
                "ticket_id": str,
                "channel": str,
                "message_id": str,
                "sent_at": str (ISO 8601),
                "delivery_status": "delivered" | "pending" | "failed",
                "error": str | None
            }

    Example:
        >>> result = send_response("TKT-20260310-4821", "Here's how to reset your password...", "email")
        >>> result["delivery_status"]
        "delivered"
    """
    valid_channels = {"email", "whatsapp", "web_form"}

    if channel not in valid_channels:
        return {
            "success": False,
            "ticket_id": ticket_id,
            "channel": channel,
            "message_id": None,
            "sent_at": datetime.utcnow().isoformat(),
            "delivery_status": "failed",
            "error": f"Invalid channel '{channel}'. Must be one of {valid_channels}",
        }

    if not message or not message.strip():
        return {
            "success": False,
            "ticket_id": ticket_id,
            "channel": channel,
            "message_id": None,
            "sent_at": datetime.utcnow().isoformat(),
            "delivery_status": "failed",
            "error": "Cannot send empty message",
        }

    message_id = f"MSG-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}"
    sent_at = datetime.utcnow().isoformat()

    # Simulate channel delivery (mock)
    channel_adapters = {
        "email": "Gmail API -> SMTP gateway",
        "whatsapp": "WhatsApp Business API -> Meta Cloud API",
        "web_form": "SyncFlow Web Response API -> Inline widget",
    }

    response_log_entry = {
        "message_id": message_id,
        "ticket_id": ticket_id,
        "channel": channel,
        "adapter": channel_adapters[channel],
        "message_preview": message[:100],
        "sent_at": sent_at,
        "delivery_status": "delivered",
    }

    _RESPONSE_LOG.append(response_log_entry)

    # Attach to ticket if it exists
    if ticket_id in _TICKET_STORE:
        _TICKET_STORE[ticket_id]["messages"].append({
            "direction": "outbound",
            "message_id": message_id,
            "content": message,
            "sent_at": sent_at,
        })

    return {
        "success": True,
        "ticket_id": ticket_id,
        "channel": channel,
        "message_id": message_id,
        "sent_at": sent_at,
        "delivery_status": "delivered",
        "error": None,
    }


# ---------------------------------------------------------------------------
# MCP Tool: escalate_to_human
# ---------------------------------------------------------------------------

def escalate_to_human(ticket_id: str, reason: str, priority: Optional[str] = None) -> dict:
    """
    MCP Tool: Escalate a ticket to the human support agent queue.

    Called when the AI agent determines it cannot — or should not —
    resolve the issue autonomously. Transfers the full conversation
    context to the human agent queue with priority routing.

    Args:
        ticket_id (str):
            The ID of the ticket being escalated (e.g., "TKT-20260310-4821").
        reason (str):
            The specific reason for escalation. This is shown to the human
            agent to provide context. Common values:
            - "high_anger_score"
            - "refund_request"
            - "pricing_negotiation"
            - "legal_threat"
            - "low_kb_confidence"
            - "unresolved_after_multiple_turns"
            - "security_incident"
            - "enterprise_renewal"
        priority (str, optional):
            Override the ticket priority for queue routing:
            "critical" | "high" | "medium" | "low"
            If not provided, inherits from the existing ticket priority.

    Returns:
        dict:
            {
                "success": bool,
                "ticket_id": str,
                "escalation_id": str,
                "reason": str,
                "priority": str,
                "assigned_queue": str,
                "human_agent": str | None,
                "estimated_response_time": str,
                "escalated_at": str (ISO 8601),
                "context_transferred": bool
            }

    Example:
        >>> result = escalate_to_human("TKT-20260310-4821", "high_anger_score", "high")
        >>> result["assigned_queue"]
        "senior-support"
    """
    # Determine queue routing based on reason
    queue_routing = {
        "legal_threat": "legal-team",
        "security_incident": "security-team",
        "pricing_negotiation": "sales-team",
        "enterprise_renewal": "enterprise-csm",
        "refund_request": "billing-team",
        "data_retention_compliance": "legal-team",
        "gdpr_compliance": "legal-team",
        "account_compromise": "security-team",
        "cancellation_churn_risk": "csm-retention",
        "high_anger_score": "senior-support",
        "persistent_frustration": "senior-support",
        "profanity_detected": "senior-support",
        "low_kb_confidence": "technical-support",
        "unresolved_after_multiple_turns": "technical-support",
        "vip_customer_negative_sentiment": "senior-support",
        "enterprise_customer_frustrated": "enterprise-csm",
        "vip_unresolved": "enterprise-csm",
    }

    queue = queue_routing.get(reason, "general-support")

    # Look up ticket
    ticket = _TICKET_STORE.get(ticket_id, {})
    effective_priority = priority or ticket.get("priority", "medium")

    # Determine estimated response time
    eta_map = {
        "critical": "within 15 minutes",
        "high": "within 1 hour",
        "medium": "within 4 hours",
        "low": "within 8 hours",
    }
    eta = eta_map.get(effective_priority, "within 4 hours")

    escalation_id = f"ESC-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}"
    escalated_at = datetime.utcnow().isoformat()

    escalation_entry = {
        "escalation_id": escalation_id,
        "ticket_id": ticket_id,
        "reason": reason,
        "priority": effective_priority,
        "assigned_queue": queue,
        "escalated_at": escalated_at,
        "context_snapshot": ticket,
    }
    _ESCALATION_LOG.append(escalation_entry)

    # Update ticket status
    if ticket_id in _TICKET_STORE:
        _TICKET_STORE[ticket_id]["status"] = "escalated"
        _TICKET_STORE[ticket_id]["assigned_to"] = "human_queue"
        _TICKET_STORE[ticket_id]["escalation_reason"] = reason
        _TICKET_STORE[ticket_id]["escalated_at"] = escalated_at

    return {
        "success": True,
        "ticket_id": ticket_id,
        "escalation_id": escalation_id,
        "reason": reason,
        "priority": effective_priority,
        "assigned_queue": queue,
        "human_agent": None,  # Assigned when a human picks it up
        "estimated_response_time": eta,
        "escalated_at": escalated_at,
        "context_transferred": True,
    }


# ---------------------------------------------------------------------------
# MCP Tool Registry (for agent tool discovery)
# ---------------------------------------------------------------------------

MCP_TOOLS = {
    "search_knowledge_base": {
        "function": search_knowledge_base,
        "description": "Search the SyncFlow knowledge base for relevant documentation and troubleshooting guides.",
        "parameters": {
            "query": {"type": "string", "required": True, "description": "Customer question or issue description"},
            "max_results": {"type": "integer", "required": False, "default": 3, "description": "Max sections to return"},
        },
    },
    "create_ticket": {
        "function": create_ticket,
        "description": "Create a new support ticket and assign it a unique ID with SLA tracking.",
        "parameters": {
            "customer_id": {"type": "string", "required": True, "description": "Customer identifier"},
            "issue": {"type": "string", "required": True, "description": "Brief description of the issue"},
            "priority": {"type": "string", "required": True, "description": "critical | high | medium | low"},
            "channel": {"type": "string", "required": True, "description": "email | whatsapp | web_form"},
            "topic": {"type": "string", "required": False, "description": "Classified issue topic"},
            "sentiment_score": {"type": "float", "required": False, "description": "Anger/frustration score 0.0–1.0"},
        },
    },
    "get_customer_history": {
        "function": get_customer_history,
        "description": "Retrieve a customer's account details, plan, and recent ticket history.",
        "parameters": {
            "customer_id": {"type": "string", "required": True, "description": "Customer identifier"},
            "limit": {"type": "integer", "required": False, "default": 5, "description": "Max recent tickets"},
        },
    },
    "send_response": {
        "function": send_response,
        "description": "Send a formatted response to the customer through their channel (email, WhatsApp, web form).",
        "parameters": {
            "ticket_id": {"type": "string", "required": True, "description": "Ticket ID to attach response to"},
            "message": {"type": "string", "required": True, "description": "Formatted message content"},
            "channel": {"type": "string", "required": True, "description": "email | whatsapp | web_form"},
        },
    },
    "escalate_to_human": {
        "function": escalate_to_human,
        "description": "Transfer a ticket to the human agent queue with full conversation context and priority routing.",
        "parameters": {
            "ticket_id": {"type": "string", "required": True, "description": "Ticket ID to escalate"},
            "reason": {"type": "string", "required": True, "description": "Escalation reason code"},
            "priority": {"type": "string", "required": False, "description": "Override priority: critical | high | medium | low"},
        },
    },
}


def list_tools() -> list:
    """
    Return a list of all available MCP tools with their descriptions and parameters.
    Used by the agent runtime for tool discovery.
    """
    return [
        {
            "name": name,
            "description": meta["description"],
            "parameters": meta["parameters"],
        }
        for name, meta in MCP_TOOLS.items()
    ]


# ---------------------------------------------------------------------------
# CLI Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=" * 60)
    print("NovaSync MCP Server — Tool Registry Demo")
    print("=" * 60)

    print("\n[1] Available Tools:")
    for tool in list_tools():
        print(f"  • {tool['name']}: {tool['description'][:60]}...")

    print("\n[2] search_knowledge_base('how to reset password'):")
    result = search_knowledge_base("how to reset password")
    for r in result["results"]:
        print(f"  [{r['relevance_score']}] {r['title']}")

    print("\n[3] get_customer_history('C-1042'):")
    history = get_customer_history("C-1042")
    print(f"  Name: {history['name']}, Plan: {history['plan']}, Health: {history['account_health']}")

    print("\n[4] create_ticket('C-1042', 'API rate limit exceeded', 'medium', 'email'):")
    ticket = create_ticket("C-1042", "API rate limit exceeded", "medium", "email", "api_rate_limit")
    print(f"  Created: {ticket['ticket_id']} | SLA: {ticket['sla_deadline']}")

    print("\n[5] send_response(ticket_id, message, 'email'):")
    send = send_response(ticket["ticket_id"], "Here is how to resolve the rate limit issue...", "email")
    print(f"  Status: {send['delivery_status']} | Message ID: {send['message_id']}")

    print("\n[6] escalate_to_human(ticket_id, 'high_anger_score', 'high'):")
    esc = escalate_to_human(ticket["ticket_id"], "high_anger_score", "high")
    print(f"  Escalation: {esc['escalation_id']} -> Queue: {esc['assigned_queue']} | ETA: {esc['estimated_response_time']}")
