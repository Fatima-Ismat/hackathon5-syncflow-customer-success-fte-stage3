"""
Agent Bridge – Stage 2
NovaSync Technologies / SyncFlow Customer Success Digital FTE

Integrates the Stage 1 AI agent with the Stage 2 backend infrastructure.

This bridge:
  1. Accepts a normalized MessagePayload from the message worker
  2. Calls the Stage 1 agent (process_customer_message)
  3. Enriches the agent result with Stage 2 metadata
  4. Returns a structured AgentResult for ticket creation and response dispatch

The bridge is the seam between prototype logic (Stage 1) and production
infrastructure (Stage 2). In Stage 3, the agent core will be upgraded to
use Claude API calls for sentiment and semantic KB search.
"""

import sys
import os
import time
from typing import Optional

# Make Stage 1 agent importable regardless of working directory
_STAGE1_PATH = os.path.join(os.path.dirname(__file__), "..", "src", "agent")
if _STAGE1_PATH not in sys.path:
    sys.path.insert(0, _STAGE1_PATH)

try:
    from customer_success_agent import process_customer_message
    STAGE1_AGENT_AVAILABLE = True
except ImportError:
    STAGE1_AGENT_AVAILABLE = False


# ---------------------------------------------------------------------------
# Agent Bridge
# ---------------------------------------------------------------------------

def run_agent(
    normalized_message: dict,
    customer: dict,
    conversation_history: Optional[list] = None,
    topic_hint: Optional[str] = None,
) -> dict:
    """
    Run the Customer Success AI agent on a normalized inbound message.

    Args:
        normalized_message:   Output from a channel adapter's normalize() call.
        customer:             Customer dict from customer_service.identify_customer().
        conversation_history: List of prior message dicts in this conversation.
        topic_hint:           Pre-classified topic from web form or routing rules.

    Returns:
        dict — AgentResult:
          response:           str — formatted reply text (channel-appropriate)
          subject_line:       str | None — email subject (email channel only)
          should_escalate:    bool
          escalation_reason:  str | None
          priority:           "critical" | "high" | "medium" | "low"
          sentiment:          str — detected sentiment label
          anger_score:        float
          frustration_score:  float
          urgency_detected:   bool
          agent_confidence:   float — KB confidence score
          kb_used:            bool
          kb_section:         str | None — matched KB section
          processing_time_ms: int
          agent_version:      str — "stage1" | "stage2_claude" (future)
    """
    start_ms = int(time.time() * 1000)

    channel        = normalized_message.get("channel", "web_form")
    raw_text       = normalized_message.get("raw_text", "")
    customer_ref   = customer.get("customer_ref", "GUEST")

    topic = topic_hint or normalized_message.get("topic_hint")

    if STAGE1_AGENT_AVAILABLE:
        result = _call_stage1_agent(
            message=raw_text,
            channel=channel,
            customer_id=customer_ref,
            topic=topic,
            conversation_history=conversation_history or [],
        )
    else:
        # Fallback: basic rule-based response when Stage 1 import fails
        result = _fallback_agent(raw_text, channel, customer, topic)

    end_ms = int(time.time() * 1000)
    processing_time_ms = end_ms - start_ms

    return {
        "response":           result.get("response", ""),
        "subject_line":       result.get("subject_line"),
        "should_escalate":    result.get("should_escalate", False),
        "escalation_reason":  result.get("escalation_reason"),
        "priority":           result.get("priority", "low"),
        "sentiment":          result.get("sentiment", "neutral"),
        "anger_score":        result.get("anger_score", 0.0),
        "frustration_score":  result.get("frustration_score", 0.0),
        "urgency_detected":   result.get("urgency_detected", False),
        "agent_confidence":   result.get("kb_confidence", 0.0),
        "kb_used":            result.get("kb_used", False),
        "kb_section":         result.get("kb_section"),
        "processing_time_ms": processing_time_ms,
        "agent_version":      "stage1" if STAGE1_AGENT_AVAILABLE else "fallback",
        "ticket_ref_hint":    result.get("ticket_id"),
    }


def compute_priority(agent_result: dict, customer: dict) -> str:
    """
    Derive final ticket priority from agent result and customer context.

    Applies business rules on top of the agent's initial priority assessment:
      - VIP customers: floor is "high" if any negative sentiment
      - Enterprise plan with urgency: floor is "high"
      - Escalated: inherit agent priority

    Args:
        agent_result: Output from run_agent().
        customer:     Customer profile dict.

    Returns:
        One of "critical" | "high" | "medium" | "low".
    """
    base_priority = agent_result.get("priority", "low")
    is_vip        = customer.get("is_vip", False)
    plan          = customer.get("plan", "starter")
    sentiment     = agent_result.get("sentiment", "neutral")
    urgency       = agent_result.get("urgency_detected", False)
    escalating    = agent_result.get("should_escalate", False)

    priority_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    final = base_priority

    if is_vip and sentiment in ("frustrated", "angry"):
        final = _max_priority(final, "high", priority_rank)

    if plan == "enterprise" and urgency:
        final = _max_priority(final, "high", priority_rank)

    if escalating and agent_result.get("escalation_reason") in (
        "legal_threat", "security_incident", "account_compromise"
    ):
        final = "critical"

    return final


def score_sentiment(agent_result: dict) -> float:
    """
    Compute a composite sentiment score from agent result signals.

    Score is 0.0 (very negative) to 1.0 (very positive).
    Used for analytics and alerting.
    """
    anger_score      = agent_result.get("anger_score", 0.0)
    frustration_score= agent_result.get("frustration_score", 0.0)
    sentiment_label  = agent_result.get("sentiment", "neutral")

    label_baseline = {
        "positive":   0.9,
        "neutral":    0.6,
        "frustrated": 0.35,
        "angry":      0.1,
    }.get(sentiment_label, 0.5)

    # Reduce baseline by anger and frustration signals
    composite = label_baseline - (anger_score * 0.2) - (frustration_score * 0.1)
    return round(max(0.0, min(1.0, composite)), 3)


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _call_stage1_agent(
    message: str,
    channel: str,
    customer_id: str,
    topic: Optional[str],
    conversation_history: list,
) -> dict:
    """Delegate to Stage 1 process_customer_message with error handling."""
    try:
        return process_customer_message(
            message=message,
            channel=channel,
            customer_id=customer_id,
            topic=topic,
            conversation_history=conversation_history,
        )
    except Exception as exc:
        return {
            "response":       f"We received your message and will follow up shortly. (Agent error: {str(exc)[:80]})",
            "should_escalate": True,
            "escalation_reason": "agent_error",
            "priority":       "medium",
            "sentiment":      "neutral",
            "kb_confidence":  0.0,
            "kb_used":        False,
        }


def _fallback_agent(
    message: str,
    channel: str,
    customer: dict,
    topic: Optional[str],
) -> dict:
    """Minimal rule-based fallback when Stage 1 import is unavailable."""
    greetings = {
        "email":    f"Hi {customer.get('name', 'there').split()[0]},\n\n",
        "whatsapp": f"Hey {customer.get('name', 'there').split()[0]}! ",
        "web_form": f"Hi {customer.get('name', 'there').split()[0]},\n\n",
    }
    greeting = greetings.get(channel, "")

    response = (
        greeting +
        "Thanks for reaching out. Our team has received your request and "
        "will get back to you shortly with a full resolution.\n\n"
        "Best,\nThe NovaSync Support Team"
    )

    return {
        "response":           response,
        "subject_line":       "Re: Your SyncFlow Support Request" if channel == "email" else None,
        "should_escalate":    True,
        "escalation_reason":  "agent_unavailable",
        "priority":           "medium",
        "sentiment":          "neutral",
        "anger_score":        0.0,
        "frustration_score":  0.0,
        "urgency_detected":   False,
        "kb_confidence":      0.0,
        "kb_used":            False,
        "kb_section":         None,
    }


def _max_priority(a: str, b: str, rank: dict) -> str:
    """Return the higher of two priority strings."""
    return a if rank.get(a, 0) >= rank.get(b, 0) else b
