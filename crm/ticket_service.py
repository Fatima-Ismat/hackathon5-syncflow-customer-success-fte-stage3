"""
Ticket Service – Stage 2
NovaSync Technologies / SyncFlow Customer Success Digital FTE

Manages the full lifecycle of customer support tickets.

Ticket States:
    OPEN → IN_PROGRESS → WAITING_CUSTOMER → RESOLVED
                       → ESCALATED → RESOLVED

Functions:
    create_ticket()          Create a new ticket with SLA assignment
    update_ticket_status()   Transition ticket through lifecycle states
    assign_priority()        Compute and assign priority from signal inputs
    resolve_ticket()         Mark resolved, record resolution time
    escalate_ticket()        Route to human queue with context

Storage: In-memory dict store (production: replace dict ops with SQLAlchemy session).
"""

import random
from datetime import datetime, timedelta
from typing import Optional

# ---------------------------------------------------------------------------
# Ticket State Machine
# ---------------------------------------------------------------------------

class TicketStatus:
    OPEN             = "open"
    IN_PROGRESS      = "in_progress"
    WAITING_CUSTOMER = "waiting_customer"
    ESCALATED        = "escalated"
    RESOLVED         = "resolved"


# Valid state transitions
VALID_TRANSITIONS: dict[str, list[str]] = {
    TicketStatus.OPEN:             [TicketStatus.IN_PROGRESS, TicketStatus.ESCALATED, TicketStatus.RESOLVED],
    TicketStatus.IN_PROGRESS:      [TicketStatus.WAITING_CUSTOMER, TicketStatus.ESCALATED, TicketStatus.RESOLVED],
    TicketStatus.WAITING_CUSTOMER: [TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED, TicketStatus.ESCALATED],
    TicketStatus.ESCALATED:        [TicketStatus.IN_PROGRESS, TicketStatus.RESOLVED],
    TicketStatus.RESOLVED:         [],  # Terminal state
}

# ---------------------------------------------------------------------------
# SLA Configuration
# ---------------------------------------------------------------------------

# Hours until SLA breach, by plan × priority
SLA_MATRIX: dict[str, dict[str, int]] = {
    "starter":    {"critical": 4,  "high": 12, "medium": 24, "low": 48},
    "growth":     {"critical": 2,  "high": 6,  "medium": 12, "low": 24},
    "business":   {"critical": 1,  "high": 2,  "medium": 4,  "low": 8},
    "enterprise": {"critical": 0.5,"high": 1,  "medium": 2,  "low": 4},
}

# Queue routing for escalation reasons
ESCALATION_QUEUE_MAP: dict[str, str] = {
    "legal_threat":                  "legal-team",
    "security_incident":             "security-team",
    "pricing_negotiation":           "sales-team",
    "enterprise_renewal":            "enterprise-csm",
    "refund_request":                "billing-team",
    "data_retention_compliance":     "legal-team",
    "gdpr_compliance":               "legal-team",
    "account_compromise":            "security-team",
    "cancellation_churn_risk":       "csm-retention",
    "high_anger_score":              "senior-support",
    "persistent_frustration":        "senior-support",
    "profanity_detected":            "senior-support",
    "low_kb_confidence":             "technical-support",
    "unresolved_after_multiple_turns": "technical-support",
    "vip_customer_negative_sentiment": "senior-support",
    "enterprise_customer_frustrated":  "enterprise-csm",
    "vip_unresolved":                  "enterprise-csm",
}

# ---------------------------------------------------------------------------
# In-Memory Store (replace with DB session in production)
# ---------------------------------------------------------------------------

_TICKET_STORE: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def create_ticket(
    customer_id: str,
    channel: str,
    issue_summary: str,
    priority: str = "medium",
    topic: Optional[str] = None,
    sentiment_at_open: Optional[str] = None,
    agent_confidence: Optional[float] = None,
    kb_used: bool = False,
    tags: Optional[list[str]] = None,
    plan: str = "starter",
) -> dict:
    """
    Create a new support ticket and assign an SLA deadline.

    Args:
        customer_id:      Customer reference (e.g., "C-1042").
        channel:          Originating channel: "email" | "whatsapp" | "web_form".
        issue_summary:    Brief description of the customer's problem.
        priority:         "critical" | "high" | "medium" | "low".
        topic:            Classified topic slug (e.g., "password_reset").
        sentiment_at_open: Sentiment label at ticket creation.
        agent_confidence: KB confidence score at time of ticket creation.
        kb_used:          Whether the knowledge base was consulted.
        tags:             List of classification tags.
        plan:             Customer plan — used to compute SLA deadline.

    Returns:
        dict — the full ticket record.
    """
    priority = _validate_priority(priority)
    ticket_ref = _generate_ticket_ref()
    now = datetime.utcnow()

    sla_hours = SLA_MATRIX.get(plan, SLA_MATRIX["starter"]).get(priority, 24)
    sla_deadline = now + timedelta(hours=sla_hours)

    ticket = {
        "ticket_ref":        ticket_ref,
        "customer_id":       customer_id,
        "channel":           channel,
        "status":            TicketStatus.OPEN,
        "priority":          priority,
        "topic":             topic,
        "tags":              tags or [],
        "issue_summary":     issue_summary,
        "assigned_to":       "ai_agent",
        "sentiment_at_open": sentiment_at_open,
        "agent_confidence":  agent_confidence,
        "kb_used":           kb_used,
        # Escalation fields
        "escalation_reason": None,
        "escalation_queue":  None,
        "escalation_id":     None,
        "escalated_at":      None,
        # SLA
        "sla_deadline":      sla_deadline.isoformat(),
        "sla_hours":         sla_hours,
        "sla_breached":      False,
        # Lifecycle timestamps
        "created_at":        now.isoformat(),
        "updated_at":        now.isoformat(),
        "resolved_at":       None,
        "resolution_time_s": None,
        # Conversation history reference
        "conversation_refs": [],
        "message_count":     0,
    }

    _TICKET_STORE[ticket_ref] = ticket
    return ticket


def update_ticket_status(
    ticket_ref: str,
    new_status: str,
    actor: str = "ai_agent",
) -> dict:
    """
    Transition a ticket to a new status, enforcing valid state transitions.

    Args:
        ticket_ref:  The ticket reference ID.
        new_status:  Target status (must be a valid next state).
        actor:       Who triggered the transition: "ai_agent" | "human:name".

    Returns:
        Updated ticket dict.

    Raises:
        ValueError: If ticket not found or transition is invalid.
    """
    ticket = _get_ticket_or_raise(ticket_ref)
    current = ticket["status"]

    allowed = VALID_TRANSITIONS.get(current, [])
    if new_status not in allowed:
        raise ValueError(
            f"Invalid transition: {current} → {new_status}. "
            f"Allowed from '{current}': {allowed}"
        )

    now = datetime.utcnow()
    ticket["status"]     = new_status
    ticket["updated_at"] = now.isoformat()
    ticket["assigned_to"] = actor

    # SLA breach check (only if not already resolved)
    if new_status != TicketStatus.RESOLVED and not ticket["sla_breached"]:
        deadline = datetime.fromisoformat(ticket["sla_deadline"])
        if now > deadline:
            ticket["sla_breached"] = True

    _TICKET_STORE[ticket_ref] = ticket
    return ticket


def assign_priority(
    sentiment_label: str,
    anger_score: float,
    urgency_detected: bool,
    topic: Optional[str],
    customer_plan: str,
    is_vip: bool,
) -> str:
    """
    Compute ticket priority from a combination of sentiment, urgency, topic, and customer tier.

    Priority matrix:
      critical — legal/security topics, or anger_score > 0.8, or VIP urgent
      high     — anger_score > 0.5, or urgency + business/enterprise plan, or VIP negative
      medium   — frustrated sentiment, or urgency on starter/growth
      low      — neutral/positive, no urgency signals

    Returns:
        One of "critical" | "high" | "medium" | "low".
    """
    CRITICAL_TOPICS = {"legal_threat", "account_compromise", "security_incident",
                       "gdpr_compliance", "legal_contract_issue"}
    HIGH_TOPICS     = {"refund_request", "enterprise_renewal", "cancellation_churn_risk",
                       "pricing_negotiation"}

    if topic in CRITICAL_TOPICS:
        return "critical"

    if anger_score >= 0.80 or (is_vip and urgency_detected):
        return "critical"

    if topic in HIGH_TOPICS:
        return "high"

    if anger_score >= 0.50:
        return "high"

    if is_vip and sentiment_label in ("frustrated", "angry"):
        return "high"

    if customer_plan in ("business", "enterprise") and urgency_detected:
        return "high"

    if sentiment_label == "frustrated" or urgency_detected:
        return "medium"

    return "low"


def resolve_ticket(
    ticket_ref: str,
    resolution_note: Optional[str] = None,
    actor: str = "ai_agent",
) -> dict:
    """
    Mark a ticket as resolved and record resolution time.

    Args:
        ticket_ref:       The ticket reference ID.
        resolution_note:  Optional summary of how the issue was resolved.
        actor:            Who resolved the ticket.

    Returns:
        Updated ticket dict with resolution metadata.
    """
    ticket = _get_ticket_or_raise(ticket_ref)

    now = datetime.utcnow()
    created = datetime.fromisoformat(ticket["created_at"])
    resolution_time_s = int((now - created).total_seconds())

    ticket["status"]           = TicketStatus.RESOLVED
    ticket["resolved_at"]      = now.isoformat()
    ticket["updated_at"]       = now.isoformat()
    ticket["resolution_time_s"] = resolution_time_s
    ticket["assigned_to"]      = actor
    if resolution_note:
        ticket["resolution_note"] = resolution_note

    # Final SLA breach check
    deadline = datetime.fromisoformat(ticket["sla_deadline"])
    ticket["sla_breached"] = now > deadline

    _TICKET_STORE[ticket_ref] = ticket
    return ticket


def escalate_ticket(
    ticket_ref: str,
    reason: str,
    priority_override: Optional[str] = None,
) -> dict:
    """
    Escalate a ticket to the appropriate human queue and update status.

    Args:
        ticket_ref:        The ticket reference ID.
        reason:            Escalation reason code (e.g., "high_anger_score").
        priority_override: Optional priority to override the current ticket priority.

    Returns:
        Updated ticket dict with escalation metadata.
    """
    ticket = _get_ticket_or_raise(ticket_ref)
    now = datetime.utcnow()

    queue = ESCALATION_QUEUE_MAP.get(reason, "general-support")
    escalation_id = f"ESC-{now.strftime('%Y%m%d%H%M%S')}-{random.randint(100, 999)}"

    if priority_override:
        ticket["priority"] = _validate_priority(priority_override)

    ticket["status"]           = TicketStatus.ESCALATED
    ticket["escalation_reason"]= reason
    ticket["escalation_queue"] = queue
    ticket["escalation_id"]    = escalation_id
    ticket["escalated_at"]     = now.isoformat()
    ticket["updated_at"]       = now.isoformat()
    ticket["assigned_to"]      = f"queue:{queue}"

    _TICKET_STORE[ticket_ref] = ticket
    return ticket


def get_ticket(ticket_ref: str) -> Optional[dict]:
    """Retrieve a ticket by reference ID. Returns None if not found."""
    return _TICKET_STORE.get(ticket_ref)


def list_tickets(
    status: Optional[str] = None,
    customer_id: Optional[str] = None,
    priority: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """
    List tickets with optional filtering.

    Returns:
        dict with 'tickets' list and 'total' count.
    """
    tickets = list(_TICKET_STORE.values())

    if status:
        tickets = [t for t in tickets if t["status"] == status]
    if customer_id:
        tickets = [t for t in tickets if t["customer_id"] == customer_id]
    if priority:
        tickets = [t for t in tickets if t["priority"] == priority]

    # Sort by created_at descending
    tickets.sort(key=lambda t: t["created_at"], reverse=True)
    total = len(tickets)

    return {
        "tickets": tickets[offset: offset + limit],
        "total":   total,
        "limit":   limit,
        "offset":  offset,
    }


def check_sla_breaches() -> list[dict]:
    """
    Scan all open tickets and flag any that have breached their SLA deadline.

    Returns:
        List of tickets that were newly flagged as SLA-breached.
    """
    now = datetime.utcnow()
    newly_breached = []

    for ticket in _TICKET_STORE.values():
        if ticket["status"] == TicketStatus.RESOLVED:
            continue
        if ticket["sla_breached"]:
            continue

        deadline = datetime.fromisoformat(ticket["sla_deadline"])
        if now > deadline:
            ticket["sla_breached"] = True
            ticket["updated_at"]   = now.isoformat()
            newly_breached.append(ticket)

    return newly_breached


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _generate_ticket_ref() -> str:
    return f"TKT-{datetime.utcnow().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"


def _validate_priority(priority: str) -> str:
    valid = {"critical", "high", "medium", "low"}
    return priority if priority in valid else "medium"


def _get_ticket_or_raise(ticket_ref: str) -> dict:
    ticket = _TICKET_STORE.get(ticket_ref)
    if not ticket:
        raise KeyError(f"Ticket not found: {ticket_ref}")
    return ticket
