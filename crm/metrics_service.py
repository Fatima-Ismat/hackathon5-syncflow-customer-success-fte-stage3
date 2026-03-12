"""
Metrics Service – Stage 2
NovaSync Technologies / SyncFlow Customer Success Digital FTE

Tracks AI agent performance metrics across:
  - Ticket volume (created, resolved, escalated)
  - Channel distribution
  - Escalation reason breakdown
  - Resolution time and SLA compliance
  - Agent confidence scores

Functions:
    record_ticket_created()    Track new ticket
    record_response_sent()     Track agent response
    record_escalation()        Track escalation with reason
    record_resolution()        Track resolution with timing
    get_metrics_summary()      Aggregate report for a time window
    get_channel_breakdown()    Per-channel volume stats

Storage: In-memory event log (production: replace with DB writes to agent_metrics table).
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional


# ---------------------------------------------------------------------------
# In-Memory Event Log
# ---------------------------------------------------------------------------

# Each event is a dict with an event_type and timestamp
_EVENT_LOG: list[dict] = []


# ---------------------------------------------------------------------------
# Recording Functions
# ---------------------------------------------------------------------------

def record_ticket_created(
    ticket_ref: str,
    customer_id: str,
    channel: str,
    priority: str,
    sentiment: str,
) -> None:
    """Record a new ticket creation event."""
    _log({
        "event_type":  "ticket_created",
        "ticket_ref":  ticket_ref,
        "customer_id": customer_id,
        "channel":     channel,
        "priority":    priority,
        "sentiment":   sentiment,
    })


def record_response_sent(
    ticket_ref: str,
    channel: str,
    agent_confidence: float,
    kb_used: bool,
    processing_time_ms: int,
) -> None:
    """Record an outbound AI agent response."""
    _log({
        "event_type":         "response_sent",
        "ticket_ref":         ticket_ref,
        "channel":            channel,
        "agent_confidence":   agent_confidence,
        "kb_used":            kb_used,
        "processing_time_ms": processing_time_ms,
    })


def record_escalation(
    ticket_ref: str,
    reason: str,
    queue: str,
    priority: str,
    channel: str,
) -> None:
    """Record a ticket escalation event."""
    _log({
        "event_type": "escalation",
        "ticket_ref": ticket_ref,
        "reason":     reason,
        "queue":      queue,
        "priority":   priority,
        "channel":    channel,
    })


def record_resolution(
    ticket_ref: str,
    resolution_time_s: int,
    channel: str,
    sla_breached: bool,
    agent_confidence: Optional[float] = None,
    kb_section_id: Optional[str] = None,
) -> None:
    """Record a ticket resolution event."""
    _log({
        "event_type":        "resolution",
        "ticket_ref":        ticket_ref,
        "resolution_time_s": resolution_time_s,
        "channel":           channel,
        "sla_breached":      sla_breached,
        "agent_confidence":  agent_confidence,
        "kb_section_id":     kb_section_id,
    })


# ---------------------------------------------------------------------------
# Query Functions
# ---------------------------------------------------------------------------

def get_metrics_summary(
    hours: int = 24,
    since: Optional[datetime] = None,
) -> dict:
    """
    Aggregate metrics for the specified time window.

    Args:
        hours: Look back N hours from now (ignored if since is provided).
        since: Optional explicit start datetime.

    Returns:
        dict with volume, quality, and breakdown metrics.
    """
    cutoff = since or (datetime.utcnow() - timedelta(hours=hours))
    events = [e for e in _EVENT_LOG if datetime.fromisoformat(e["ts"]) >= cutoff]

    tickets_created     = sum(1 for e in events if e["event_type"] == "ticket_created")
    responses_generated = sum(1 for e in events if e["event_type"] == "response_sent")
    escalations         = sum(1 for e in events if e["event_type"] == "escalation")
    resolutions         = sum(1 for e in events if e["event_type"] == "resolution")

    # SLA breaches
    sla_breaches = sum(
        1 for e in events
        if e["event_type"] == "resolution" and e.get("sla_breached")
    )

    # Avg resolution time
    resolution_times = [
        e["resolution_time_s"] for e in events
        if e["event_type"] == "resolution" and e.get("resolution_time_s") is not None
    ]
    avg_resolution_time_s = (
        round(sum(resolution_times) / len(resolution_times), 1)
        if resolution_times else None
    )

    # Avg agent confidence
    confidences = [
        e["agent_confidence"] for e in events
        if e["event_type"] == "response_sent" and e.get("agent_confidence") is not None
    ]
    avg_agent_confidence = (
        round(sum(confidences) / len(confidences), 3)
        if confidences else None
    )

    # Channel breakdown
    channel_usage: dict[str, int] = defaultdict(int)
    for e in events:
        if e.get("channel"):
            channel_usage[e["channel"]] += 1

    # Escalation reason breakdown
    escalation_reasons: dict[str, int] = defaultdict(int)
    for e in events:
        if e["event_type"] == "escalation" and e.get("reason"):
            escalation_reasons[e["reason"]] += 1

    # Escalation queue breakdown
    escalation_queues: dict[str, int] = defaultdict(int)
    for e in events:
        if e["event_type"] == "escalation" and e.get("queue"):
            escalation_queues[e["queue"]] += 1

    # KB usage rate
    kb_responses = [e for e in events if e["event_type"] == "response_sent"]
    kb_used_count = sum(1 for e in kb_responses if e.get("kb_used"))
    kb_usage_rate = (
        round(kb_used_count / len(kb_responses), 3)
        if kb_responses else None
    )

    # Auto-resolution rate (resolved without escalation)
    auto_resolution_rate = None
    if tickets_created > 0:
        auto_resolutions = resolutions - escalations
        auto_resolution_rate = round(max(auto_resolutions, 0) / tickets_created, 3)

    return {
        "window_hours":           hours,
        "since":                  cutoff.isoformat(),
        "generated_at":           datetime.utcnow().isoformat(),
        "volume": {
            "tickets_created":     tickets_created,
            "responses_generated": responses_generated,
            "escalations":         escalations,
            "resolutions":         resolutions,
            "sla_breaches":        sla_breaches,
        },
        "quality": {
            "avg_resolution_time_s": avg_resolution_time_s,
            "avg_agent_confidence":  avg_agent_confidence,
            "kb_usage_rate":         kb_usage_rate,
            "auto_resolution_rate":  auto_resolution_rate,
            "escalation_rate": (
                round(escalations / tickets_created, 3)
                if tickets_created > 0 else None
            ),
        },
        "channel_usage":       dict(channel_usage),
        "escalation_reasons":  dict(escalation_reasons),
        "escalation_queues":   dict(escalation_queues),
    }


def get_channel_breakdown(hours: int = 24) -> dict:
    """
    Per-channel volume and quality metrics for the last N hours.

    Returns:
        dict mapping channel → {tickets, responses, escalations, avg_confidence}
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    events = [e for e in _EVENT_LOG if datetime.fromisoformat(e["ts"]) >= cutoff]

    channels = {"email", "whatsapp", "web_form"}
    breakdown = {}

    for ch in channels:
        ch_events = [e for e in events if e.get("channel") == ch]
        tickets    = sum(1 for e in ch_events if e["event_type"] == "ticket_created")
        responses  = sum(1 for e in ch_events if e["event_type"] == "response_sent")
        escalations = sum(1 for e in ch_events if e["event_type"] == "escalation")

        confidences = [
            e["agent_confidence"] for e in ch_events
            if e["event_type"] == "response_sent" and e.get("agent_confidence") is not None
        ]

        breakdown[ch] = {
            "tickets":          tickets,
            "responses":        responses,
            "escalations":      escalations,
            "avg_confidence":   round(sum(confidences) / len(confidences), 3) if confidences else None,
        }

    return {
        "window_hours": hours,
        "channels":     breakdown,
        "generated_at": datetime.utcnow().isoformat(),
    }


def get_sentiment_distribution(hours: int = 24) -> dict:
    """
    Distribution of sentiment labels across inbound tickets.

    Returns:
        dict mapping sentiment label → count and percentage.
    """
    cutoff = datetime.utcnow() - timedelta(hours=hours)
    events = [
        e for e in _EVENT_LOG
        if e["event_type"] == "ticket_created"
        and datetime.fromisoformat(e["ts"]) >= cutoff
        and e.get("sentiment")
    ]

    counts: dict[str, int] = defaultdict(int)
    for e in events:
        counts[e["sentiment"]] += 1

    total = sum(counts.values())
    distribution = {
        label: {"count": count, "pct": round(count / total * 100, 1) if total else 0.0}
        for label, count in counts.items()
    }

    return {
        "window_hours":  hours,
        "total_tickets": total,
        "distribution":  distribution,
        "generated_at":  datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _log(event: dict) -> None:
    """Append a timestamped event to the in-memory log."""
    event["ts"] = datetime.utcnow().isoformat()
    _EVENT_LOG.append(event)
