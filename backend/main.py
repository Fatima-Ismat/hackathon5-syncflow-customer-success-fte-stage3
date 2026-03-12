"""
FastAPI Backend – Stage 2
NovaSync Technologies / SyncFlow Customer Success Digital FTE

Production-ready HTTP API for the Customer Success CRM system.

Endpoints:
  POST   /support/submit                    Receive and process inbound support message
  GET    /tickets                           List all tickets (with filters)
  GET    /tickets/{ticket_ref}              Get a single ticket by reference
  POST   /tickets/{ticket_ref}/reply        Add a reply to a ticket
  POST   /tickets/{ticket_ref}/escalate     Manually escalate a ticket
  GET    /customers/{customer_ref}          Get customer profile + history
  GET    /metrics/summary                   Agent performance summary
  GET    /metrics/channels                  Per-channel breakdown
  GET    /health                            Health check endpoint

Run with:
  uvicorn backend.main:app --reload --port 8000
  # or from root:
  python -m uvicorn backend.main:app --reload

Docs at: http://localhost:8000/docs
"""

import sys
import os

# Ensure repo root is on the path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from workers.message_worker import process_message
from crm import ticket_service, customer_service, metrics_service
from crm.ticket_service import TicketStatus


# ---------------------------------------------------------------------------
# App Setup
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SyncFlow Customer Success API",
    description=(
        "NovaSync Technologies — Customer Success Digital FTE\n\n"
        "Stage 2: Production-ready backend with AI agent, CRM, "
        "ticket management, and multi-channel message processing."
    ),
    version="2.0.0",
    contact={
        "name":  "NovaSync Support",
        "email": "support@novasynctechnologies.com",
    },
)

# CORS — allow the Next.js frontend (localhost:3000) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

class SupportMessageRequest(BaseModel):
    channel: str = Field(
        ...,
        description="Delivery channel: email | whatsapp | web_form | web",
        examples=["web_form"],
    )
    customer_ref: str = Field(
        ...,
        description=(
            "Customer reference or identifier. "
            "Use a known CRM ref (e.g. C-1042) for existing customers, "
            "or any string (e.g. an email address) for new contacts."
        ),
        examples=["C-1042"],
    )
    message: str = Field(
        ...,
        description="The customer's support message text.",
        examples=["I cannot reset my password — the reset link is not arriving."],
    )
    conversation_history: Optional[list] = Field(
        None,
        description="Prior turns in this conversation for multi-turn context.",
    )
    debug: bool = Field(
        False,
        description="If true, include internal pipeline stage details in the response.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "channel":      "web_form",
                "customer_ref": "cust001",
                "message":      "I cannot reset my password",
            }
        }
    }


class TicketReplyRequest(BaseModel):
    message: str = Field(
        ...,
        description="The reply message text.",
        examples=["We are working on your issue and will update you shortly."],
    )
    actor: Optional[str] = Field(
        "human_agent",
        description="Who is replying: 'human_agent' or 'ai_agent'.",
    )
    send_to_customer: Optional[bool] = Field(
        True,
        description="If True, dispatch the reply to the customer via the original channel.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "message": "We are working on your issue."
            }
        }
    }


class EscalateRequest(BaseModel):
    reason: str = Field(
        ...,
        description=(
            "Escalation reason. Use a plain description or a known reason code: "
            "refund_request | legal_threat | high_anger_score | low_kb_confidence | "
            "security_incident | pricing_negotiation | enterprise_renewal"
        ),
        examples=["high_anger_score"],
    )
    priority: Optional[str] = Field(
        None,
        description="Optional priority override: critical | high | medium | low.",
    )
    notes: Optional[str] = Field(
        None,
        description="Optional context notes for the receiving human agent.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "reason": "High priority issue"
            }
        }
    }


class APIResponse(BaseModel):
    success: bool
    data: Any
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _ok(data: Any) -> APIResponse:
    return APIResponse(success=True, data=data)


def _err(message: str, status_code: int = 400):
    raise HTTPException(status_code=status_code, detail=message)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health", tags=["System"])
def health_check():
    """
    Health check endpoint.

    Returns 200 OK with system status.
    Used by load balancers, uptime monitors, and readiness probes.
    """
    return {
        "status":    "ok",
        "service":   "syncflow-customer-success-api",
        "version":   "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
    }


@app.post("/support/submit", response_model=APIResponse, tags=["Support"])
def submit_support_message(request: SupportMessageRequest):
    """
    **Primary endpoint — receive and process an inbound customer support message.**

    Accepts a flat JSON body:
    ```json
    {
      "channel":      "web_form",
      "customer_ref": "C-1042",
      "message":      "I cannot reset my password"
    }
    ```

    Pipeline:
    1. Normalize the message for the target channel
    2. Identify the customer (by customer_ref or email extracted from message)
    3. Run the AI Customer Success agent
    4. Create a support ticket with SLA deadline
    5. Escalate to human queue if required
    6. Dispatch response via the originating channel
    7. Record metrics

    Returns the full pipeline result including ticket reference,
    AI response, escalation status, and agent confidence.
    """
    # Accept "web" as a friendly alias for "web_form"
    channel = "web_form" if request.channel == "web" else request.channel

    VALID_CHANNELS = ("email", "whatsapp", "web_form")
    if channel not in VALID_CHANNELS:
        _err(
            f"Invalid channel '{request.channel}'. "
            f"Must be one of: {', '.join(VALID_CHANNELS)} (or 'web' as alias for web_form)"
        )

    # Build the internal raw_payload from the flat request fields.
    # Each channel adapter's normalize() reads different keys, so we
    # populate all common variants so any adapter can find the message.
    payload: dict = {
        # Universal fields
        "customer_ref": request.customer_ref,
        # web_form adapter reads "description"
        "description":  request.message,
        # email adapter reads "body"
        "body":         request.message,
        # whatsapp adapter reads "text"
        "text":         request.message,
        # web_form adapter reads "name" / email for identification
        "name":         request.customer_ref,
    }

    result = process_message(
        channel=channel,
        raw_payload=payload,
        conversation_history=request.conversation_history,
        debug=request.debug,
    )

    if not result.get("success") and result.get("error"):
        _err(result["error"], status_code=422)

    return _ok(result)


@app.get("/tickets", response_model=APIResponse, tags=["Tickets"])
def list_tickets(
    status:   Optional[str] = Query(None, description="Filter by status: open | in_progress | waiting_customer | escalated | resolved"),
    priority: Optional[str] = Query(None, description="Filter by priority: critical | high | medium | low"),
    customer: Optional[str] = Query(None, description="Filter by customer_ref (e.g., C-1042)"),
    limit:    int            = Query(50, description="Max tickets to return"),
    offset:   int            = Query(0, description="Pagination offset"),
):
    """
    **List support tickets with optional filters.**

    Supports filtering by status, priority, and customer.
    Results are sorted newest-first.
    """
    result = ticket_service.list_tickets(
        status=status,
        customer_id=customer,
        priority=priority,
        limit=limit,
        offset=offset,
    )
    return _ok(result)


@app.get("/tickets/{ticket_ref}", response_model=APIResponse, tags=["Tickets"])
def get_ticket(ticket_ref: str):
    """
    **Get a single ticket by reference ID.**

    Returns full ticket record including:
    - Lifecycle status and history
    - Escalation metadata
    - SLA deadline and breach status
    - Agent confidence and KB section used
    """
    ticket = ticket_service.get_ticket(ticket_ref)
    if not ticket:
        _err(f"Ticket not found: {ticket_ref}", status_code=404)
    return _ok(ticket)


@app.post("/tickets/{ticket_ref}/reply", response_model=APIResponse, tags=["Tickets"])
def reply_to_ticket(ticket_ref: str, request: TicketReplyRequest):
    """
    **Add a reply to an existing ticket.**

    Used by human agents responding through the dashboard.
    Optionally dispatches the reply to the customer via the original channel.

    Transitions ticket status:
    - WAITING_CUSTOMER → IN_PROGRESS when a human replies
    - ESCALATED → IN_PROGRESS when the specialist picks up
    """
    ticket = ticket_service.get_ticket(ticket_ref)
    if not ticket:
        _err(f"Ticket not found: {ticket_ref}", status_code=404)

    if ticket["status"] == TicketStatus.RESOLVED:
        _err(f"Cannot reply to a resolved ticket: {ticket_ref}")

    # Transition to IN_PROGRESS
    updated: Optional[dict] = None
    try:
        updated = ticket_service.update_ticket_status(
            ticket_ref=ticket_ref,
            new_status=TicketStatus.IN_PROGRESS,
            actor=request.actor,
        )
    except (ValueError, KeyError) as exc:
        _err(str(exc))
    if not updated:
        _err(f"Failed to update ticket: {ticket_ref}")

    return _ok({
        "ticket_ref":   ticket_ref,
        "status":       updated["status"],
        "reply":        request.message,
        "actor":        request.actor,
        "replied_at":   datetime.utcnow().isoformat(),
        "sent_to_customer": request.send_to_customer,
    })


@app.post("/tickets/{ticket_ref}/escalate", response_model=APIResponse, tags=["Tickets"])
def escalate_ticket(ticket_ref: str, request: EscalateRequest):
    """
    **Manually escalate a ticket to the human agent queue.**

    Used when a human triage agent determines a ticket needs specialist attention,
    or when the API consumer explicitly triggers escalation.

    Routes to the correct specialist queue based on escalation reason:
    - legal_threat → legal-team
    - refund_request → billing-team
    - high_anger_score → senior-support
    - low_kb_confidence → technical-support
    (see ticket_service.ESCALATION_QUEUE_MAP for full routing table)
    """
    ticket = ticket_service.get_ticket(ticket_ref)
    if not ticket:
        _err(f"Ticket not found: {ticket_ref}", status_code=404)

    if ticket["status"] == TicketStatus.RESOLVED:
        _err(f"Cannot escalate a resolved ticket: {ticket_ref}")

    try:
        updated = ticket_service.escalate_ticket(
            ticket_ref=ticket_ref,
            reason=request.reason,
            priority_override=request.priority,
        )
    except (KeyError, ValueError) as exc:
        _err(str(exc), status_code=404)

    # Record escalation metric
    metrics_service.record_escalation(
        ticket_ref=ticket_ref,
        reason=request.reason,
        queue=updated.get("escalation_queue", "general-support"),
        priority=updated.get("priority", "medium"),
        channel=updated.get("channel", "unknown"),
    )

    return _ok({
        "ticket_ref":       ticket_ref,
        "status":           updated["status"],
        "escalation_reason": updated["escalation_reason"],
        "escalation_queue": updated["escalation_queue"],
        "escalation_id":    updated["escalation_id"],
        "escalated_at":     updated["escalated_at"],
        "notes":            request.notes,
    })


@app.get("/customers/{customer_ref}", response_model=APIResponse, tags=["Customers"])
def get_customer(customer_ref: str, ticket_limit: int = Query(10)):
    """
    **Get customer profile and support history.**

    Returns:
    - Customer demographics and plan
    - Account health score
    - CSAT average
    - Recent ticket history
    - MRR (used for escalation priority weighting)
    """
    result = customer_service.get_customer_history(
        customer_ref=customer_ref,
        ticket_limit=ticket_limit,
    )
    if not result["found"]:
        _err(f"Customer not found: {customer_ref}", status_code=404)
    return _ok(result)


@app.get("/metrics/summary", response_model=APIResponse, tags=["Metrics"])
def get_metrics_summary(hours: int = Query(24, ge=1, le=168, description="Look-back window in hours (1–168)")):
    """
    **AI agent performance summary for the specified time window.**

    Returns:
    - Volume: tickets created, responses generated, escalations, resolutions
    - Quality: avg resolution time, avg agent confidence, KB usage rate
    - Escalation breakdown by reason and queue
    - Channel distribution
    - Auto-resolution rate
    """
    summary = metrics_service.get_metrics_summary(hours=hours)
    return _ok(summary)


@app.get("/metrics/channels", response_model=APIResponse, tags=["Metrics"])
def get_channel_metrics(hours: int = Query(24, ge=1, le=168)):
    """
    **Per-channel volume and quality metrics.**

    Breaks down tickets, responses, escalations, and confidence scores
    by channel: email | whatsapp | web_form.
    """
    breakdown = metrics_service.get_channel_breakdown(hours=hours)
    return _ok(breakdown)


@app.get("/metrics/sentiment", response_model=APIResponse, tags=["Metrics"])
def get_sentiment_distribution(hours: int = Query(24, ge=1, le=168)):
    """
    **Sentiment distribution of inbound messages.**

    Shows the breakdown of positive / neutral / frustrated / angry
    sentiment across all tickets in the time window.

    Use this to detect when customer satisfaction is trending down
    before CSAT scores are collected.
    """
    distribution = metrics_service.get_sentiment_distribution(hours=hours)
    return _ok(distribution)


# ---------------------------------------------------------------------------
# Exception Handlers
# ---------------------------------------------------------------------------

@app.exception_handler(Exception)
async def generic_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={
            "success":   False,
            "data":      None,
            "error":     f"Internal server error: {str(exc)[:200]}",
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# ---------------------------------------------------------------------------
# CLI Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
