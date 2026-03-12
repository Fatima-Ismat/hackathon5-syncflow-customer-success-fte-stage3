"""
Customer Success AI Agent – Stage 1 Prototype
NovaSync Technologies / SyncFlow Support

This module implements the core customer success agent logic for Stage 1 incubation.
It is intentionally kept as a clear, readable prototype — not production code.

The agent:
  - Accepts customer messages from any supported channel
  - Identifies the customer and loads their context
  - Detects sentiment to calibrate response tone
  - Searches the knowledge base for answers
  - Decides whether to escalate to a human
  - Formats the response to match the channel style

Channels supported: email | whatsapp | web_form
"""

import json
import re
import os
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration & Constants
# ---------------------------------------------------------------------------

SUPPORTED_CHANNELS = {"email", "whatsapp", "web_form"}

# Knowledge base loaded from context file (in production: vector DB)
KB_FILE = os.path.join(os.path.dirname(__file__), "../../context/product-docs.md")

# Sample customer registry (in production: CRM API call)
MOCK_CUSTOMER_DB = {
    "C-1042": {"name": "Marcus Chen",    "plan": "growth",    "is_vip": False, "open_tickets": 0},
    "C-2817": {"name": "Priya Nair",     "plan": "starter",   "is_vip": False, "open_tickets": 1},
    "C-3301": {"name": "James Whitfield","plan": "business",  "is_vip": False, "open_tickets": 0},
    "C-4451": {"name": "Sofia Reyes",    "plan": "growth",    "is_vip": False, "open_tickets": 0},
    "C-5103": {"name": "David Okafor",   "plan": "starter",   "is_vip": False, "open_tickets": 2},
    "C-6229": {"name": "Lena Hoffmann",  "plan": "business",  "is_vip": True,  "open_tickets": 0},
    "C-8901": {"name": "Angela Torres",  "plan": "enterprise","is_vip": True,  "open_tickets": 0},
}

# Sentiment keyword signals
ANGER_KEYWORDS = [
    "ridiculous", "unacceptable", "furious", "outraged", "lawsuit",
    "lawyer", "legal", "disgusting", "terrible", "awful", "pathetic",
    "useless", "scam", "fraud", "broken", "worst", "hate"
]
FRUSTRATION_KEYWORDS = [
    "still", "again", "days", "hours", "waiting", "no response",
    "nothing works", "keeps failing", "same issue", "not fixed",
    "been trying", "multiple times"
]
URGENCY_KEYWORDS = [
    "urgent", "asap", "immediately", "right now", "losing money",
    "shut down", "critical", "emergency", "down", "outage"
]
PROFANITY_KEYWORDS = ["damn", "hell", "crap", "shit", "fuck", "bastard", "idiot"]

# Escalation topic triggers
IMMEDIATE_ESCALATION_TOPICS = {
    "refund_request", "legal_contract_issue", "account_compromise",
    "pricing_negotiation", "gdpr_compliance", "data_retention_compliance",
    "security_documentation", "enterprise_renewal", "cancellation_churn_risk",
    "legal_threat"
}

# Channel format profiles
CHANNEL_PROFILES = {
    "email": {
        "tone": "formal",
        "max_words": 300,
        "greeting": "Hi {name},",
        "closing": "\nBest,\nThe NovaSync Support Team",
        "use_bullets": True,
    },
    "whatsapp": {
        "tone": "conversational",
        "max_words": 80,
        "greeting": "Hey {name}!",
        "closing": "",
        "use_bullets": False,
    },
    "web_form": {
        "tone": "semi-formal",
        "max_words": 200,
        "greeting": "Hi {name},",
        "closing": "\nLet us know if you have any other questions.",
        "use_bullets": True,
    },
}


# ---------------------------------------------------------------------------
# 1. process_customer_message()
# ---------------------------------------------------------------------------

def process_customer_message(
    message: str,
    channel: str,
    customer_id: str,
    topic: Optional[str] = None,
    conversation_history: Optional[list] = None,
) -> dict:
    """
    Main entry point for the customer success agent.

    Accepts an inbound customer message and orchestrates the full
    processing pipeline: identify -> sentiment -> knowledge search ->
    escalation decision -> format response.

    Args:
        message:              The raw customer message text.
        channel:              One of "email", "whatsapp", "web_form".
        customer_id:          Customer identifier string (e.g., "C-1042").
        topic:                Optional pre-classified topic string.
        conversation_history: Optional list of prior message dicts.

    Returns:
        A dict containing:
          - response:         The formatted reply to send to the customer.
          - should_escalate:  Boolean indicating escalation is required.
          - escalation_reason: Reason string if escalating, else None.
          - priority:         "critical" | "high" | "medium" | "low"
          - ticket_id:        Generated ticket reference.
          - sentiment:        Detected sentiment label.
          - channel:          The channel this was processed for.
    """
    if not message or not message.strip():
        return _empty_message_response(channel, customer_id)

    if channel not in SUPPORTED_CHANNELS:
        raise ValueError(f"Unsupported channel: '{channel}'. Must be one of {SUPPORTED_CHANNELS}")

    conversation_history = conversation_history or []

    # Step 1: Load customer context
    customer = _get_customer(customer_id)

    # Step 2: Detect sentiment
    sentiment_result = detect_sentiment(message, conversation_history)

    # Step 3: Check immediate escalation rules
    escalation_result = decide_escalation(
        sentiment_result=sentiment_result,
        topic=topic,
        customer=customer,
        conversation_turn=len(conversation_history),
        message=message,
    )

    # Step 4: If immediate escalation, skip knowledge search
    if escalation_result["tier"] == 1:
        response_text = _build_escalation_acknowledgment(customer, channel)
        formatted = format_response_for_channel(
            raw_response=response_text,
            channel=channel,
            customer_name=customer.get("name", "there"),
            is_escalation=True,
        )
        ticket_id = _generate_ticket_id()
        return {
            "ticket_id": ticket_id,
            "channel": channel,
            "customer_id": customer_id,
            "sentiment": sentiment_result["sentiment"],
            "should_escalate": True,
            "escalation_reason": escalation_result["reason"],
            "priority": escalation_result["priority"],
            "response": formatted["response"],
            "subject_line": formatted.get("subject_line"),
            "kb_used": False,
            "timestamp": datetime.utcnow().isoformat(),
        }

    # Step 5: Search knowledge base
    kb_result = search_knowledge_base(message, channel=channel)

    # Step 6: Re-evaluate escalation with KB confidence
    if kb_result["confidence"] < 0.40 and not escalation_result["should_escalate"]:
        escalation_result["should_escalate"] = True
        escalation_result["reason"] = "low_kb_confidence"
        escalation_result["priority"] = "medium"

    # Step 7: Generate raw response content
    if escalation_result["should_escalate"]:
        raw_response = _build_escalation_acknowledgment(customer, channel)
    else:
        raw_response = _compose_response(
            kb_result=kb_result,
            message=message,
            topic=topic,
            channel=channel,
        )

    # Step 8: Format for channel
    formatted = format_response_for_channel(
        raw_response=raw_response,
        channel=channel,
        customer_name=customer.get("name", "there"),
        topic=topic,
        is_escalation=escalation_result["should_escalate"],
    )

    ticket_id = _generate_ticket_id()

    return {
        "ticket_id": ticket_id,
        "channel": channel,
        "customer_id": customer_id,
        "sentiment": sentiment_result["sentiment"],
        "should_escalate": escalation_result["should_escalate"],
        "escalation_reason": escalation_result.get("reason"),
        "priority": escalation_result["priority"],
        "response": formatted["response"],
        "subject_line": formatted.get("subject_line"),
        "kb_confidence": kb_result["confidence"],
        "kb_section": kb_result.get("section"),
        "kb_used": kb_result["answer_found"],
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# 2. search_knowledge_base()
# ---------------------------------------------------------------------------

def search_knowledge_base(query: str, channel: str = "email", max_results: int = 3) -> dict:
    """
    Search the SyncFlow product documentation for relevant content.

    This Stage 1 implementation uses simple keyword matching against the
    markdown documentation. In Stage 2 this will be replaced with a
    vector embedding search (e.g., using Claude + embeddings API).

    Args:
        query:       The customer's question or issue description.
        channel:     Used to weight brevity vs. detail of extracted answer.
        max_results: Maximum number of document sections to consider.

    Returns:
        dict with keys:
          - answer_found:  bool
          - answer:        str — extracted answer text
          - confidence:    float 0.0–1.0
          - section:       str — document section that matched
          - snippets:      list[str] — relevant text excerpts
    """
    if not query or not query.strip():
        return {"answer_found": False, "answer": "", "confidence": 0.0,
                "section": None, "snippets": []}

    query_lower = query.lower()
    query_tokens = set(re.findall(r'\b\w+\b', query_lower))

    # Knowledge base topic map: keywords -> section + canned answer
    kb_entries = [
        {
            "keywords": {"password", "reset", "forgot", "login", "locked"},
            "section": "Password & Security -> Password Reset",
            "answer": (
                "To reset your password:\n"
                "1. Go to app.syncflow.io/login\n"
                "2. Click 'Forgot Password'\n"
                "3. Enter your email address\n"
                "4. Check your inbox — the reset link is valid for 60 minutes\n"
                "5. Create a new password (min 12 characters, uppercase + number + symbol)\n\n"
                "Note: After reset, all active sessions are terminated. You'll need to log in again."
            ),
        },
        {
            "keywords": {"2fa", "two-factor", "authenticator", "otp", "verification", "invalid code"},
            "section": "Password & Security -> Two-Factor Authentication",
            "answer": (
                "If your 2FA code is showing as invalid:\n"
                "1. Ensure your phone's time is synced correctly (authenticator apps are time-sensitive)\n"
                "2. Try a fresh code — don't use one that is more than 30 seconds old\n"
                "3. If using SMS, check for any network delay\n"
                "4. Supported apps: Google Authenticator, Authy, 1Password, Microsoft Authenticator\n\n"
                "To enable 2FA: Settings -> Security -> Two-Factor Authentication -> Enable"
            ),
        },
        {
            "keywords": {"api", "key", "401", "403", "429", "rate", "limit", "unauthorized", "forbidden"},
            "section": "API Usage -> API Keys & Error Codes",
            "answer": (
                "Common API errors:\n"
                "• 401 Unauthorized: Your API key is invalid or expired. Regenerate it at Settings -> Developer -> API Keys\n"
                "• 403 Forbidden: The key exists but lacks permission for this action. Check key scope\n"
                "• 429 Too Many Requests: You've hit the rate limit. Wait for X-RateLimit-Reset or upgrade your plan\n\n"
                "Rate limits by plan: Starter 60 req/min | Growth 300 req/min | Business 1,000 req/min"
            ),
        },
        {
            "keywords": {"billing", "invoice", "charge", "payment", "refund", "subscription", "cost", "price"},
            "section": "Billing & Subscriptions",
            "answer": (
                "Billing details:\n"
                "• Invoices are generated on the 1st of each month (Settings -> Billing -> Invoice History)\n"
                "• Upgrading takes effect immediately with a prorated charge for the remainder of the cycle\n"
                "• Downgrading takes effect at the start of the next billing cycle\n"
                "• Refund policy: Annual plans -> pro-rated refund within 30 days; Monthly plans -> no refund for current period\n\n"
                "For refund requests, contact billing@novasynctechnologies.com"
            ),
        },
        {
            "keywords": {"salesforce", "hubspot", "slack", "google", "sheets", "oauth", "connect", "integration"},
            "section": "Integrations -> Connecting an Integration",
            "answer": (
                "To connect an integration:\n"
                "1. Dashboard -> Integrations -> Browse\n"
                "2. Search for the app\n"
                "3. Click Connect -> Authorize via OAuth\n"
                "4. Configure field mapping and sync settings\n"
                "5. Test the connection\n\n"
                "If OAuth fails with 'redirect_uri_mismatch': clear browser cookies and try again. "
                "If the error persists, try a different browser."
            ),
        },
        {
            "keywords": {"oauth", "token", "expired", "reconnect", "session", "invalid_session"},
            "section": "Integrations -> OAuth Token Expiry",
            "answer": (
                "OAuth tokens expire periodically for security reasons. When this happens:\n"
                "• You'll see a 'Reconnect Required' banner on the affected integration\n"
                "• Affected workflows will fail and generate error logs\n\n"
                "Fix: Integrations -> [App] -> Reconnect -> Re-authorize with the external service. "
                "Your workflows will resume automatically."
            ),
        },
        {
            "keywords": {"workflow", "trigger", "not", "firing", "stopped", "scheduled", "paused"},
            "section": "Troubleshooting -> Workflow Not Triggering",
            "answer": (
                "If your workflow isn't triggering:\n"
                "1. Confirm the workflow status is Active (not Paused or Draft)\n"
                "2. Verify the trigger conditions are correctly configured\n"
                "3. For webhook triggers: check if the source app's webhook is still registered\n"
                "4. For scheduled triggers: confirm the timezone setting is correct\n"
                "5. Check your plan's monthly automation run limit hasn't been reached\n\n"
                "Check run history: Workflows -> [Workflow Name] -> Run History"
            ),
        },
        {
            "keywords": {"webhook", "duplicate", "firing", "twice", "multiple", "retry"},
            "section": "API Usage -> Webhooks",
            "answer": (
                "Duplicate webhook events can occur if:\n"
                "• Your endpoint did not return a 200 OK fast enough, triggering a retry\n"
                "• SyncFlow's retry policy (1m, 5m, 30m, 2h, 12h) fired for a perceived failure\n\n"
                "Solution: Ensure your endpoint responds with 200 within 5 seconds. "
                "Implement idempotency using the event ID in the X-SyncFlow-Event-ID header "
                "to deduplicate on your end."
            ),
        },
        {
            "keywords": {"sso", "saml", "okta", "azure", "google workspace", "single sign", "login"},
            "section": "Password & Security -> Single Sign-On",
            "answer": (
                "SSO is available on Business and Enterprise plans.\n"
                "Supported providers: Okta, Azure AD, Google Workspace, OneLogin\n\n"
                "Common SSO issues:\n"
                "• 'SSO not configured': Enable it in Settings -> Security -> SSO\n"
                "• Email domain mismatch: Confirm your email matches the configured domain\n"
                "• Redirect loop: Clear cookies and try incognito mode\n\n"
                "SSO requires Admin access to configure. Contact your IT administrator."
            ),
        },
        {
            "keywords": {"export", "data", "download", "cancel", "cancellation", "delete", "backup"},
            "section": "Data & Privacy -> Exporting Your Data",
            "answer": (
                "To export your account data:\n"
                "Settings -> Data -> Export Account Data\n\n"
                "Your export includes: workflows, run history, team settings, integration configs, and custom fields.\n"
                "Processing time: up to 2 hours for large accounts.\n\n"
                "After cancellation, data is retained for 90 days before permanent deletion."
            ),
        },
        {
            "keywords": {"seat", "member", "invite", "team", "viewer", "admin", "role", "permission"},
            "section": "Account Management -> Managing Team Members",
            "answer": (
                "Team roles:\n"
                "• Admin: Full account access including billing\n"
                "• Member: Access to assigned workspaces only\n"
                "• Viewer: Read-only access to shared dashboards\n\n"
                "To invite: Settings -> Team -> Invite Members -> Enter email -> Select role -> Send Invite\n"
                "Invites expire after 7 days. Seat limits: Starter 5 | Growth 25 | Business 100 | Enterprise unlimited"
            ),
        },
        {
            "keywords": {"workspace", "department", "project", "client", "isolated"},
            "section": "Account Management -> Workspaces",
            "answer": (
                "Workspaces are isolated environments within your account.\n"
                "Create up to: Starter 3 | Growth 10 | Business/Enterprise unlimited\n\n"
                "To create: Dashboard -> New Workspace -> Name -> Set permissions"
            ),
        },
    ]

    # Score each KB entry
    scored = []
    for entry in kb_entries:
        overlap = query_tokens & entry["keywords"]
        if overlap:
            score = len(overlap) / max(len(entry["keywords"]), 1)
            # Boost for exact phrase matches
            for kw in entry["keywords"]:
                if kw in query_lower:
                    score += 0.15
            scored.append((min(score, 1.0), entry))

    if not scored:
        return {
            "answer_found": False,
            "answer": "",
            "confidence": 0.15,
            "section": None,
            "snippets": [],
        }

    # Sort by confidence descending
    scored.sort(key=lambda x: x[0], reverse=True)
    best_score, best_entry = scored[0]

    return {
        "answer_found": best_score >= 0.30,
        "answer": best_entry["answer"],
        "confidence": round(best_score, 2),
        "section": best_entry["section"],
        "snippets": [best_entry["answer"][:200]],
    }


# ---------------------------------------------------------------------------
# 3. detect_sentiment()
# ---------------------------------------------------------------------------

def detect_sentiment(message: str, conversation_history: Optional[list] = None) -> dict:
    """
    Analyze the emotional tone of a customer message.

    Uses keyword-based heuristics for Stage 1 prototype.
    In Stage 2, this will be replaced by a Claude API call
    with structured sentiment classification.

    Args:
        message:              The customer's raw message text.
        conversation_history: List of prior message dicts for trend detection.

    Returns:
        dict with keys:
          - sentiment:           "positive" | "neutral" | "frustrated" | "angry"
          - anger_score:         float 0.0–1.0
          - frustration_score:   float 0.0–1.0
          - urgency_detected:    bool
          - profanity_detected:  bool
          - caps_ratio:          float (ratio of caps to total chars)
          - tone_flags:          list[str]
    """
    conversation_history = conversation_history or []
    text_lower = message.lower()
    tone_flags = []

    # Caps lock detection
    alpha_chars = [c for c in message if c.isalpha()]
    caps_ratio = sum(1 for c in alpha_chars if c.isupper()) / max(len(alpha_chars), 1)
    if caps_ratio > 0.4 and len(alpha_chars) > 10:
        tone_flags.append("excessive_caps")

    # Exclamation mark overuse
    exclamation_count = message.count("!")
    if exclamation_count >= 3:
        tone_flags.append("exclamation_overuse")

    # Profanity check — use word boundaries to avoid "hello" matching "hell"
    profanity_detected = any(
        re.search(r'\b' + re.escape(word) + r'\b', text_lower)
        for word in PROFANITY_KEYWORDS
    )
    if profanity_detected:
        tone_flags.append("profanity")

    # Urgency detection
    urgency_detected = any(word in text_lower for word in URGENCY_KEYWORDS)
    if urgency_detected:
        tone_flags.append("urgency")

    # Anger scoring — use word boundaries to avoid substring false positives
    anger_hits = sum(
        1 for word in ANGER_KEYWORDS
        if re.search(r'\b' + re.escape(word) + r'\b', text_lower)
    )
    anger_score = min(anger_hits * 0.18, 1.0)
    if caps_ratio > 0.30:   # lowered threshold: captures "THIS IS RIDICULOUS" style
        anger_score = min(anger_score + 0.25, 1.0)
    if exclamation_count >= 3:
        anger_score = min(anger_score + 0.10, 1.0)
    if profanity_detected:
        anger_score = min(anger_score + 0.35, 1.0)

    # Frustration scoring
    frustration_hits = sum(1 for word in FRUSTRATION_KEYWORDS if word in text_lower)
    frustration_score = min(frustration_hits * 0.15, 1.0)
    # Check conversation history for repeated frustration
    if len(conversation_history) >= 2:
        frustration_score = min(frustration_score + 0.20, 1.0)

    # Determine overall sentiment label
    if anger_score >= 0.65 or profanity_detected:
        sentiment = "angry"
    elif frustration_score >= 0.45 or anger_score >= 0.35:
        sentiment = "frustrated"
    elif any(word in text_lower for word in ["thank", "great", "love", "awesome", "amazing", "helpful"]):
        sentiment = "positive"
    else:
        sentiment = "neutral"

    return {
        "sentiment": sentiment,
        "anger_score": round(anger_score, 2),
        "frustration_score": round(frustration_score, 2),
        "urgency_detected": urgency_detected,
        "profanity_detected": profanity_detected,
        "caps_ratio": round(caps_ratio, 2),
        "tone_flags": tone_flags,
    }


# ---------------------------------------------------------------------------
# 4. decide_escalation()
# ---------------------------------------------------------------------------

def decide_escalation(
    sentiment_result: dict,
    topic: Optional[str],
    customer: dict,
    conversation_turn: int = 0,
    message: str = "",
) -> dict:
    """
    Determine whether the current ticket should be escalated to a human agent.

    Evaluates multiple signals: topic classification, sentiment thresholds,
    customer tier, conversation history length, and message content.

    Args:
        sentiment_result:  Output from detect_sentiment().
        topic:             Issue topic string (e.g., "refund_request").
        customer:          Customer dict with plan, is_vip, etc.
        conversation_turn: Number of prior exchanges in this conversation.
        message:           Raw message for additional keyword scanning.

    Returns:
        dict with keys:
          - should_escalate:  bool
          - reason:           str — human-readable escalation reason
          - priority:         "critical" | "high" | "medium" | "low"
          - tier:             1 | 2 | 3 (escalation tier level)
    """
    plan = customer.get("plan", "starter")
    is_vip = customer.get("is_vip", False)
    message_lower = message.lower()

    # --- TIER 1: Immediate escalation ---

    # Legal threats in message — use word boundaries to avoid "issue" matching "sue"
    legal_signals = ["lawsuit", "lawyer", "legal action", r"\bsue\b", "court", "regulatory", "gdpr complaint"]
    if any(re.search(signal, message_lower) for signal in legal_signals):
        return {"should_escalate": True, "reason": "legal_threat", "priority": "critical", "tier": 1}

    # Security/breach signals
    breach_signals = ["unauthorized access", "hacked", r"\bbreach\b", "data leak", "someone else logged in"]
    if any(re.search(signal, message_lower) for signal in breach_signals):
        return {"should_escalate": True, "reason": "security_incident", "priority": "critical", "tier": 1}

    # Immediate escalation topics
    if topic in IMMEDIATE_ESCALATION_TOPICS:
        priority_map = {
            "legal_contract_issue": "critical",
            "account_compromise": "critical",
            "cancellation_churn_risk": "high",
            "enterprise_renewal": "high",
            "refund_request": "high",
            "pricing_negotiation": "medium",
            "gdpr_compliance": "high",
            "data_retention_compliance": "high",
            "security_documentation": "high",
        }
        priority = priority_map.get(topic, "medium")
        return {"should_escalate": True, "reason": topic, "priority": priority, "tier": 1}

    # Profanity or extreme anger
    if sentiment_result.get("profanity_detected"):
        return {"should_escalate": True, "reason": "profanity_detected", "priority": "high", "tier": 1}

    if sentiment_result.get("anger_score", 0) >= 0.75:
        return {"should_escalate": True, "reason": "high_anger_score", "priority": "high", "tier": 1}

    # --- TIER 2: Escalate after one attempt ---

    if sentiment_result.get("frustration_score", 0) >= 0.70 and conversation_turn >= 2:
        return {"should_escalate": True, "reason": "persistent_frustration", "priority": "medium", "tier": 2}

    if conversation_turn >= 4:
        return {"should_escalate": True, "reason": "unresolved_after_multiple_turns", "priority": "medium", "tier": 2}

    # VIP customers get lower escalation threshold
    if is_vip and sentiment_result.get("sentiment") in ("frustrated", "angry"):
        return {"should_escalate": True, "reason": "vip_customer_negative_sentiment", "priority": "high", "tier": 2}

    # Enterprise plan with frustration
    if plan == "enterprise" and sentiment_result.get("sentiment") == "frustrated":
        return {"should_escalate": True, "reason": "enterprise_customer_frustrated", "priority": "medium", "tier": 2}

    # --- TIER 3: Judgment-based ---

    if is_vip and conversation_turn >= 2:
        return {"should_escalate": True, "reason": "vip_unresolved", "priority": "low", "tier": 3}

    # No escalation
    return {"should_escalate": False, "reason": None, "priority": "low", "tier": 0}


# ---------------------------------------------------------------------------
# 5. format_response_for_channel()
# ---------------------------------------------------------------------------

def format_response_for_channel(
    raw_response: str,
    channel: str,
    customer_name: str = "there",
    topic: Optional[str] = None,
    is_escalation: bool = False,
) -> dict:
    """
    Format and adapt a response to match the communication style of the channel.

    Applies channel-specific tone, length limits, greeting/closing templates,
    and structural formatting (bullets, numbered lists, plain text).

    Args:
        raw_response:   The content to be sent — the core answer text.
        channel:        "email" | "whatsapp" | "web_form"
        customer_name:  Customer's first name for personalized greeting.
        topic:          Issue topic — used to generate email subject lines.
        is_escalation:  Whether this response is an escalation acknowledgment.

    Returns:
        dict with keys:
          - response:      str — the final formatted message to send
          - subject_line:  str — email subject line (email channel only)
          - word_count:    int
          - format_type:   str — "formal" | "conversational" | "structured"
    """
    if channel not in CHANNEL_PROFILES:
        channel = "web_form"

    profile = CHANNEL_PROFILES[channel]
    first_name = customer_name.split()[0] if customer_name else "there"

    # Build greeting
    greeting = profile["greeting"].format(name=first_name)
    closing = profile["closing"]

    if channel == "whatsapp":
        # WhatsApp: strip formatting, keep very brief
        response = _format_whatsapp(raw_response, greeting)
    elif channel == "email":
        response = _format_email(raw_response, greeting, closing)
    else:
        # Web form: semi-formal, with structure
        response = _format_web_form(raw_response, greeting, closing)

    # Enforce word limit
    words = response.split()
    if len(words) > profile["max_words"]:
        words = words[:profile["max_words"]]
        response = " ".join(words) + "..."

    # Generate email subject line
    subject_line = None
    if channel == "email":
        subject_line = _generate_subject_line(topic, is_escalation)

    return {
        "response": response,
        "subject_line": subject_line,
        "word_count": len(response.split()),
        "format_type": profile["tone"],
    }


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _format_whatsapp(content: str, greeting: str) -> str:
    """Convert content to short, conversational WhatsApp message."""
    # Remove markdown bullet formatting
    lines = content.replace("•", "-").split("\n")
    clean_lines = [line.strip() for line in lines if line.strip()]
    # Take only the first 2 meaningful lines for brevity
    short = " ".join(clean_lines[:3])
    # Strip numbered list formatting
    short = re.sub(r'^\d+\.\s+', '', short)
    return f"{greeting} {short}"


def _format_email(content: str, greeting: str, closing: str) -> str:
    """Format content as a professional email."""
    return f"{greeting}\n\n{content}{closing}"


def _format_web_form(content: str, greeting: str, closing: str) -> str:
    """Format content as a structured web form response."""
    return f"{greeting}\n\n{content}{closing}"


def _generate_subject_line(topic: Optional[str], is_escalation: bool = False) -> str:
    """Generate an email subject line from the topic."""
    if is_escalation:
        return "Re: Your Support Request – Connecting You With Our Team"
    topic_map = {
        "password_reset": "Re: Password Reset Assistance",
        "billing_question": "Re: Billing Inquiry",
        "api_rate_limit": "Re: API Rate Limit — Next Steps",
        "api_authentication": "Re: API Authentication Issue",
        "integration_oauth_error": "Re: Integration OAuth Issue",
        "workflow_not_triggering": "Re: Workflow Trigger Troubleshooting",
        "account_compromise": "Re: Account Security — Urgent",
        "2fa_issue": "Re: Two-Factor Authentication Help",
        "login_issue": "Re: Login Assistance",
        "webhook_issue": "Re: Webhook Configuration",
        "data_export": "Re: Data Export Instructions",
    }
    return topic_map.get(topic or "", "Re: Your SyncFlow Support Request")


def _compose_response(
    kb_result: dict,
    message: str,
    topic: Optional[str],
    channel: str,
) -> str:
    """Build the core response body from KB results."""
    if kb_result.get("answer_found") and kb_result.get("answer"):
        return kb_result["answer"]

    # Fallback when KB has low confidence but didn't trigger escalation
    return (
        "I want to make sure I give you the most accurate answer here. "
        "Could you share a bit more detail about the issue you're experiencing? "
        "For example, any error messages you're seeing or the steps you've already tried would help."
    )


def _build_escalation_acknowledgment(customer: dict, channel: str) -> str:
    """Build the body text for an escalation handoff message."""
    plan = customer.get("plan", "starter")
    sla_map = {
        "starter": "within 24 hours",
        "growth": "within 8 hours",
        "business": "within 2 hours",
        "enterprise": "within 1 hour",
    }
    sla = sla_map.get(plan, "as soon as possible")

    if channel == "whatsapp":
        return f"I'm connecting you with a specialist who can help with this directly. You'll hear back {sla}."
    else:
        return (
            "I want to make sure you get the best possible support here. I'm connecting you "
            f"with one of our specialized team members who will follow up with you {sla}.\n\n"
            "Your full conversation history has been shared with them so you won't need to repeat yourself."
        )


def _get_customer(customer_id: str) -> dict:
    """Retrieve customer details from mock database."""
    return MOCK_CUSTOMER_DB.get(customer_id, {
        "name": "Valued Customer",
        "plan": "starter",
        "is_vip": False,
        "open_tickets": 0,
    })


def _generate_ticket_id() -> str:
    """Generate a unique ticket ID."""
    import random
    return f"TKT-{datetime.utcnow().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"


def _empty_message_response(channel: str, customer_id: str) -> dict:
    """Handle empty or blank message input gracefully."""
    clarification = {
        "email": "Thank you for reaching out. It looks like your message came through empty. Could you reply with your question and we'll get right on it?",
        "whatsapp": "Hey! Looks like your message was empty. What can we help you with?",
        "web_form": "Hi there, it looks like your message was blank. Please describe your issue and we'll be happy to help.",
    }
    return {
        "ticket_id": _generate_ticket_id(),
        "channel": channel,
        "customer_id": customer_id,
        "sentiment": "neutral",
        "should_escalate": False,
        "escalation_reason": None,
        "priority": "low",
        "response": clarification.get(channel, "It looks like your message was empty. How can we help?"),
        "subject_line": "Re: Your Support Request" if channel == "email" else None,
        "kb_used": False,
        "timestamp": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# CLI Demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    """Quick smoke test — run with: python customer_success_agent.py"""

    test_cases = [
        {
            "message": "hi how do i reset my password i forgot it",
            "channel": "whatsapp",
            "customer_id": "C-2817",
            "topic": "password_reset",
        },
        {
            "message": "THIS IS RIDICULOUS I've been waiting 3 DAYS and nobody has helped me!!! My entire business is DOWN!!!",
            "channel": "whatsapp",
            "customer_id": "C-3356",
            "topic": "angry_customer",
        },
        {
            "message": "Hello Support Team,\n\nI am getting a 429 rate limit error on all API calls. My plan is Growth and I need this resolved urgently.\n\nBest,\nMarcus",
            "channel": "email",
            "customer_id": "C-1042",
            "topic": "api_rate_limit",
        },
        {
            "message": "Issue Type: Billing\n\nI noticed a $47.22 charge that I didn't expect. Can you explain?\n\nAccount: j.whitfield@techbridge.com",
            "channel": "web_form",
            "customer_id": "C-3301",
            "topic": "billing_question",
        },
    ]

    print("=" * 70)
    print("NovaSync Customer Success Agent — Stage 1 Prototype Demo")
    print("=" * 70)

    for i, tc in enumerate(test_cases, 1):
        print(f"\n--- Test Case {i}: {tc['topic'].upper()} ({tc['channel']}) ---")
        print(f"Input: {tc['message'][:80]}...")
        result = process_customer_message(**tc)
        print(f"Ticket:     {result['ticket_id']}")
        print(f"Sentiment:  {result['sentiment']}")
        print(f"Escalate:   {result['should_escalate']} ({result.get('escalation_reason', 'N/A')})")
        print(f"Priority:   {result['priority']}")
        if result.get("subject_line"):
            print(f"Subject:    {result['subject_line']}")
        print(f"Response:\n{result['response']}")
        print("-" * 70)
