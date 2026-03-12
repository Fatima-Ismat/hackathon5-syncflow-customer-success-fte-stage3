"""
Message Worker – Stage 2
NovaSync Technologies / SyncFlow Customer Success Digital FTE

Implements the full message processing pipeline:

    Channel Input
        → Normalization      (channel adapter)
        → Customer ID        (customer_service)
        → AI Agent           (agent_bridge)
        → Ticket Management  (ticket_service)
        → Metrics Recording  (metrics_service)
        → Response Dispatch  (channel adapter)

This worker is the central orchestrator for all inbound support messages.
It is channel-agnostic — any channel feeds the same pipeline.

In production, this would be invoked by:
  - A FastAPI endpoint (synchronous path for low-latency channels)
  - A Celery/RQ task queue (async path for email processing)
  - An event-driven consumer (Kafka/SQS for high-volume WhatsApp)

Current implementation runs synchronously in-process for the hackathon demo.
"""

import time
from datetime import datetime
from typing import Optional

# Channel adapters
from channels import email_channel, whatsapp_channel, web_form_channel

# CRM services
from crm import customer_service, ticket_service, knowledge_service, metrics_service

# Agent bridge (Stage 1 + Stage 2 integration)
from backend.agent_bridge import run_agent, compute_priority, score_sentiment


# ---------------------------------------------------------------------------
# Channel Adapter Registry
# ---------------------------------------------------------------------------

CHANNEL_ADAPTERS = {
    "email":    email_channel,
    "whatsapp": whatsapp_channel,
    "web_form": web_form_channel,
}


# ---------------------------------------------------------------------------
# Primary Entry Point
# ---------------------------------------------------------------------------

def process_message(
    channel: str,
    raw_payload: dict,
    conversation_history: Optional[list] = None,
    debug: bool = False,
) -> dict:
    """
    Process a single inbound customer support message end-to-end.

    Pipeline:
      1. Validate channel and select adapter
      2. Normalize payload (channel → standard format)
      3. Identify customer (email / phone / account_id / customer_ref)
      4. Run AI agent (Stage 1 logic via agent_bridge)
      5. Create or update support ticket
      6. Escalate if required
      7. Record metrics
      8. Dispatch response via channel adapter
      9. Return pipeline result

    Args:
        channel:              "email" | "whatsapp" | "web_form"
        raw_payload:          Raw inbound payload from the channel.
        conversation_history: Prior messages in this conversation (for multi-turn).
        debug:                If True, include intermediate pipeline stages in result.

    Returns:
        dict — PipelineResult:
          success:            bool — True if pipeline completed without fatal error
          ticket_ref:         str — ticket reference (e.g., TKT-20260311-1234)
          response:           str — the reply sent to the customer
          subject_line:       str | None — email subject if applicable
          should_escalate:    bool
          escalation_reason:  str | None
          priority:           str
          sentiment:          str
          agent_confidence:   float
          kb_section:         str | None
          processing_time_ms: int
          pipeline_stages:    dict (only present if debug=True)
          error:              str | None — error message if success=False
    """
    pipeline_start = int(time.time() * 1000)
    stages = {}

    # ------------------------------------------------------------------
    # Stage 1: Validate channel
    # ------------------------------------------------------------------
    if channel not in CHANNEL_ADAPTERS:
        return _error_result(
            f"Unsupported channel: '{channel}'. Must be one of {list(CHANNEL_ADAPTERS.keys())}",
            channel=channel,
        )

    adapter = CHANNEL_ADAPTERS[channel]

    # ------------------------------------------------------------------
    # Stage 2: Normalize payload
    # ------------------------------------------------------------------
    try:
        normalized = adapter.normalize(raw_payload)
        stages["normalize"] = {"status": "ok", "channel": channel}
    except Exception as exc:
        return _error_result(f"Normalization failed: {exc}", channel=channel)

    if not normalized.get("raw_text", "").strip():
        return _empty_message_result(channel, normalized)

    # ------------------------------------------------------------------
    # Stage 3: Identify customer
    # ------------------------------------------------------------------
    id_result = customer_service.identify_customer(
        customer_ref=raw_payload.get("customer_ref") or normalized.get("account_id"),
        email=normalized.get("sender_email"),
        phone=normalized.get("sender_phone"),
        whatsapp_number=normalized.get("sender_phone") if channel == "whatsapp" else None,
        name=normalized.get("sender_name"),
    )

    customer = id_result["customer"]
    stages["identify_customer"] = {
        "status":       "ok",
        "found":        id_result["found"],
        "match_method": id_result["match_method"],
        "customer_ref": customer.get("customer_ref"),
        "plan":         customer.get("plan"),
    }

    # ------------------------------------------------------------------
    # Stage 4: Run AI agent
    # ------------------------------------------------------------------
    topic_hint = normalized.get("topic_hint") or raw_payload.get("topic")

    agent_result = run_agent(
        normalized_message=normalized,
        customer=customer,
        conversation_history=conversation_history or [],
        topic_hint=topic_hint,
    )

    stages["agent"] = {
        "status":          "ok",
        "sentiment":       agent_result["sentiment"],
        "should_escalate": agent_result["should_escalate"],
        "confidence":      agent_result["agent_confidence"],
        "agent_version":   agent_result["agent_version"],
    }

    # ------------------------------------------------------------------
    # Stage 5: Compute final priority
    # ------------------------------------------------------------------
    priority = compute_priority(agent_result, customer)
    sentiment_score = score_sentiment(agent_result)

    # ------------------------------------------------------------------
    # Stage 6: Create ticket
    # ------------------------------------------------------------------
    issue_summary = _build_issue_summary(normalized, agent_result)
    tags = _build_tags(normalized, agent_result, customer)

    ticket = ticket_service.create_ticket(
        customer_id=customer.get("customer_ref", "GUEST"),
        channel=channel,
        issue_summary=issue_summary,
        priority=priority,
        topic=topic_hint,
        sentiment_at_open=agent_result["sentiment"],
        agent_confidence=agent_result["agent_confidence"],
        kb_used=agent_result["kb_used"],
        tags=tags,
        plan=customer.get("plan", "starter"),
    )
    ticket_ref = ticket["ticket_ref"]

    # Transition to IN_PROGRESS immediately
    ticket_service.update_ticket_status(ticket_ref, ticket_service.TicketStatus.IN_PROGRESS)

    stages["ticket"] = {
        "status":     "ok",
        "ticket_ref": ticket_ref,
        "priority":   priority,
        "sla_hours":  ticket.get("sla_hours"),
    }

    # ------------------------------------------------------------------
    # Stage 7: Escalate if required
    # ------------------------------------------------------------------
    if agent_result["should_escalate"]:
        escalation_result = ticket_service.escalate_ticket(
            ticket_ref=ticket_ref,
            reason=agent_result["escalation_reason"] or "unclassified",
            priority_override=priority,
        )
        stages["escalation"] = {
            "status": "ok",
            "queue":  escalation_result.get("escalation_queue"),
            "reason": agent_result["escalation_reason"],
        }

        metrics_service.record_escalation(
            ticket_ref=ticket_ref,
            reason=agent_result["escalation_reason"] or "unclassified",
            queue=escalation_result.get("escalation_queue", "general-support"),
            priority=priority,
            channel=channel,
        )
    else:
        # Mark resolved if agent handled it autonomously
        ticket_service.update_ticket_status(
            ticket_ref, ticket_service.TicketStatus.WAITING_CUSTOMER
        )

    # ------------------------------------------------------------------
    # Stage 8: Record metrics
    # ------------------------------------------------------------------
    metrics_service.record_ticket_created(
        ticket_ref=ticket_ref,
        customer_id=customer.get("customer_ref", "GUEST"),
        channel=channel,
        priority=priority,
        sentiment=agent_result["sentiment"],
    )

    metrics_service.record_response_sent(
        ticket_ref=ticket_ref,
        channel=channel,
        agent_confidence=agent_result["agent_confidence"],
        kb_used=agent_result["kb_used"],
        processing_time_ms=agent_result["processing_time_ms"],
    )

    # Update customer stats
    customer_service.update_customer_stats(
        customer_ref=customer.get("customer_ref", "GUEST"),
        open_delta=1,
        total_delta=1,
    )

    # ------------------------------------------------------------------
    # Stage 9: Dispatch response
    # ------------------------------------------------------------------
    dispatch_result = _dispatch_response(
        channel=channel,
        adapter=adapter,
        normalized=normalized,
        response_text=agent_result["response"],
        subject_line=agent_result.get("subject_line"),
        ticket_ref=ticket_ref,
    )

    stages["dispatch"] = {
        "status":          "ok" if dispatch_result.get("success") else "failed",
        "delivery_status": dispatch_result.get("delivery_status"),
    }

    # ------------------------------------------------------------------
    # Final result
    # ------------------------------------------------------------------
    pipeline_ms = int(time.time() * 1000) - pipeline_start

    result = {
        "success":           True,
        "ticket_ref":        ticket_ref,
        "customer_ref":      customer.get("customer_ref"),
        "customer_name":     customer.get("name"),
        "customer_plan":     customer.get("plan"),
        "channel":           channel,
        "response":          agent_result["response"],
        "subject_line":      agent_result.get("subject_line"),
        "should_escalate":   agent_result["should_escalate"],
        "escalation_reason": agent_result.get("escalation_reason"),
        "escalation_queue":  stages.get("escalation", {}).get("queue"),
        "priority":          priority,
        "sentiment":         agent_result["sentiment"],
        "sentiment_score":   sentiment_score,
        "agent_confidence":  agent_result["agent_confidence"],
        "kb_used":           agent_result["kb_used"],
        "kb_section":        agent_result.get("kb_section"),
        "sla_deadline":      ticket.get("sla_deadline"),
        "processing_time_ms": pipeline_ms,
        "processed_at":      datetime.utcnow().isoformat(),
        "error":             None,
    }

    if debug:
        result["pipeline_stages"] = stages

    return result


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _dispatch_response(
    channel: str,
    adapter,
    normalized: dict,
    response_text: str,
    subject_line: Optional[str],
    ticket_ref: str,
) -> dict:
    """Route the response to the correct channel adapter's send_reply function."""
    try:
        if channel == "email":
            return adapter.send_reply(
                to_email=normalized.get("sender_email", ""),
                to_name=normalized.get("sender_name", ""),
                subject=subject_line or "Re: Your SyncFlow Support Request",
                body=response_text,
                thread_id=normalized.get("thread_id"),
                ticket_ref=ticket_ref,
            )
        elif channel == "whatsapp":
            return adapter.send_reply(
                to_phone=normalized.get("sender_phone", ""),
                body=response_text,
                ticket_ref=ticket_ref,
                reply_to_wamid=normalized.get("external_id"),
            )
        else:  # web_form
            return adapter.send_reply(
                session_id=normalized.get("thread_id"),
                body=response_text,
                ticket_ref=ticket_ref,
                sender_email=normalized.get("sender_email"),
            )
    except Exception as exc:
        return {"success": False, "delivery_status": "failed", "error": str(exc)}


def _build_issue_summary(normalized: dict, agent_result: dict) -> str:
    """Construct a concise issue summary from normalized message and agent analysis."""
    raw_text = normalized.get("raw_text", "")
    # Use first 150 chars of the message as the summary
    summary = raw_text[:150].strip()
    if len(raw_text) > 150:
        summary += "..."
    return summary or "No description provided"


def _build_tags(normalized: dict, agent_result: dict, customer: dict) -> list[str]:
    """Build a list of classification tags for the ticket."""
    tags = []

    # From web form metadata
    meta_tags = normalized.get("metadata", {}).get("tags", [])
    tags.extend(meta_tags)

    # Sentiment tags
    sentiment = agent_result.get("sentiment", "neutral")
    if sentiment in ("frustrated", "angry"):
        tags.append(sentiment)
    if agent_result.get("urgency_detected"):
        tags.append("urgent")

    # Customer tier tags
    if customer.get("is_vip"):
        tags.append("vip")
    plan = customer.get("plan", "starter")
    if plan in ("business", "enterprise"):
        tags.append(plan)

    # Escalation tag
    if agent_result.get("should_escalate"):
        tags.append("escalated")

    # Channel tag
    tags.append(normalized.get("channel", "unknown"))

    return list(set(tags))  # deduplicate


def _error_result(message: str, channel: str = "unknown") -> dict:
    """Return a standardized error result for pipeline failures."""
    return {
        "success":           False,
        "ticket_ref":        None,
        "channel":           channel,
        "response":          None,
        "should_escalate":   False,
        "priority":          "medium",
        "sentiment":         "neutral",
        "processing_time_ms": 0,
        "processed_at":      datetime.utcnow().isoformat(),
        "error":             message,
    }


def _empty_message_result(channel: str, normalized: dict) -> dict:
    """Handle empty message payloads gracefully."""
    clarifications = {
        "email":    "Thank you for reaching out. Your message appears to be empty. Please reply with your question and we'll get right on it.",
        "whatsapp": "Hey! It looks like your message was empty. What can we help you with?",
        "web_form": "Hi — it looks like your support form came through without a description. Please re-submit with details about your issue.",
    }
    return {
        "success":           True,
        "ticket_ref":        None,
        "channel":           channel,
        "response":          clarifications.get(channel, "Your message was empty. How can we help?"),
        "should_escalate":   False,
        "priority":          "low",
        "sentiment":         "neutral",
        "agent_confidence":  0.0,
        "kb_used":           False,
        "processing_time_ms": 0,
        "processed_at":      datetime.utcnow().isoformat(),
        "error":             None,
    }
