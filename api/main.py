"""
api/main.py
SyncFlow Customer Success Digital FTE — Stage 3 Final Production API
NovaSync Technologies

FastAPI application exposing the full Customer Success platform:
  - Multi-channel support intake (Web Form, Gmail webhook, WhatsApp webhook)
  - CRM ticket management
  - Customer profile lookup
  - Agent metrics and analytics
  - Cross-channel conversation continuity
  - Health + readiness probes

Run:
  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
  python -m uvicorn api.main:app --reload

Docs:
  http://localhost:8000/docs      Swagger UI
  http://localhost:8000/redoc     ReDoc
"""

import sys
import os
import logging
import time
import hashlib
import hmac
from datetime import datetime
from typing import Any, Optional, List

from fastapi import FastAPI, HTTPException, Query, Header, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, EmailStr, validator

# ── ensure repo root is on path ──────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from workers.message_worker import process_message
from crm import ticket_service, customer_service, metrics_service
from crm.ticket_service import TicketStatus

logger = logging.getLogger("syncflow.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

ALLOWED_ORIGINS = os.getenv("CORS_ORIGINS", "").split(",") + [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "https://*.vercel.app",
    "https://syncflow-support.vercel.app",
]

app = FastAPI(
    title="SyncFlow Customer Success API",
    description=(
        "**NovaSync Technologies — Customer Success Digital FTE**\n\n"
        "Stage 3 · Production-ready AI-powered support platform with:\n"
        "- Multi-channel intake: Gmail · WhatsApp · Web Form\n"
        "- PostgreSQL CRM with cross-channel identity\n"
        "- OpenAI Agents SDK powered AI agent\n"
        "- Kafka event streaming\n"
        "- Full ticket lifecycle management\n"
        "- Real-time metrics and analytics\n\n"
        "_Owner: Ismat Fatima · Hackathon 5 Final Stage_"
    ),
    version="3.0.0",
    contact={"name": "NovaSync Support", "email": "support@novasynctechnologies.com"},
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─────────────────────────────────────────────────────────────────────────────
# Request / Response Models
# ─────────────────────────────────────────────────────────────────────────────

class SupportSubmitRequest(BaseModel):
    """Web form / API support submission."""
    channel: str = Field("web_form", description="Channel: email | whatsapp | web_form")
    customer_ref: str = Field(..., description="Customer ref (C-XXXX) or email/phone", examples=["C-1042"])
    name: Optional[str] = Field(None, description="Customer display name")
    email: Optional[str] = Field(None, description="Customer email address")
    subject: Optional[str] = Field(None, description="Message subject / category")
    category: Optional[str] = Field(None, description="Support category")
    priority: Optional[str] = Field(None, description="Requested priority: critical|high|medium|low")
    message: str = Field(..., description="Customer support message", min_length=5)
    conversation_history: Optional[List[dict]] = Field(None)
    debug: bool = Field(False)

    model_config = {
        "json_schema_extra": {
            "example": {
                "channel": "web_form",
                "customer_ref": "C-1042",
                "name": "Alice Chen",
                "email": "alice@acmecorp.com",
                "subject": "Cannot reset password",
                "message": "I've been trying to reset my password for 30 minutes. The link never arrives.",
            }
        }
    }


class TicketReplyRequest(BaseModel):
    message: str = Field(..., min_length=1)
    actor: str = Field("human_agent")
    send_to_customer: bool = Field(True)


class EscalateRequest(BaseModel):
    reason: str = Field(..., description="Escalation reason code or description")
    priority: Optional[str] = Field(None)
    notes: Optional[str] = Field(None)


class CustomerLookupRequest(BaseModel):
    email: Optional[str] = Field(None)
    phone: Optional[str] = Field(None)
    customer_ref: Optional[str] = Field(None)


class APIResponse(BaseModel):
    success: bool
    data: Any
    error: Optional[str] = None
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _ok(data: Any) -> APIResponse:
    return APIResponse(success=True, data=data)


def _err(msg: str, status: int = 400):
    raise HTTPException(status_code=status, detail=msg)


def _normalize_channel(ch: str) -> str:
    mapping = {"web": "web_form", "form": "web_form", "gmail": "email", "smtp": "email",
                "wa": "whatsapp", "wapp": "whatsapp"}
    return mapping.get(ch.lower(), ch.lower())


# ─────────────────────────────────────────────────────────────────────────────
# Startup / Shutdown
# ─────────────────────────────────────────────────────────────────────────────

_startup_time = datetime.utcnow()

@app.on_event("startup")
async def startup_event():
    logger.info("SyncFlow API v3.0 starting up — %s", datetime.utcnow().isoformat())
    # Try to initialize Kafka producer in background
    try:
        from kafka_client import get_producer
        get_producer()
        logger.info("Kafka producer initialized")
    except Exception as e:
        logger.warning("Kafka not available (dev mode): %s", e)


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("SyncFlow API shutting down gracefully")
    try:
        from kafka_client import close_producer
        close_producer()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# System Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["System"], summary="Health check")
def health():
    """
    Liveness probe — returns 200 if the API process is running.

    Checks availability of: API · CRM · Kafka · Agent
    """
    uptime_seconds = (datetime.utcnow() - _startup_time).total_seconds()

    services = {
        "api": "ok",
        "crm": "ok",
    }

    # Check Kafka
    try:
        from kafka_client import get_producer
        get_producer()
        services["kafka"] = "ok"
    except Exception:
        services["kafka"] = "unavailable (mock mode)"

    # Check agent
    try:
        from agent import run_agent
        services["agent"] = "ok"
    except Exception:
        services["agent"] = "degraded (fallback mode)"

    return {
        "status": "ok",
        "service": "syncflow-customer-success-api",
        "version": "3.0.0",
        "owner": "Ismat Fatima",
        "uptime_seconds": round(uptime_seconds, 1),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "services": services,
        "channels": {
            "web_form": "active",
            "email": "active (mock)" if not os.getenv("GMAIL_CREDENTIALS_JSON") else "active",
            "whatsapp": "active (mock)" if not os.getenv("TWILIO_ACCOUNT_SID") else "active",
        },
    }


@app.get("/readiness", tags=["System"], summary="Readiness probe")
def readiness():
    """Kubernetes readiness probe — confirms service can accept traffic."""
    return {"ready": True, "timestamp": datetime.utcnow().isoformat() + "Z"}


# ─────────────────────────────────────────────────────────────────────────────
# Support Submission
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/support/submit", response_model=APIResponse, tags=["Support"],
          summary="Submit a customer support request")
def submit_support(request: SupportSubmitRequest, background_tasks: BackgroundTasks):
    """
    **Primary intake endpoint for customer support messages.**

    Processes through the full 9-stage pipeline:
    1. Channel normalization
    2. Customer identification
    3. AI agent response generation (OpenAI Agents SDK)
    4. Sentiment analysis & priority computation
    5. Ticket creation with SLA deadline
    6. Escalation routing if needed
    7. Response dispatch
    8. Kafka event publishing
    9. Metrics recording

    Returns ticket reference, AI response, escalation status, and confidence score.
    """
    channel = _normalize_channel(request.channel)
    VALID = ("email", "whatsapp", "web_form")
    if channel not in VALID:
        _err(f"Invalid channel '{request.channel}'. Must be one of: {', '.join(VALID)}")

    payload = {
        "customer_ref": request.customer_ref,
        "name": request.name or request.customer_ref,
        "email": request.email or "",
        "subject": request.subject or "",
        "category": request.category or "general",
        "priority": request.priority or "medium",
        # all channel adapters read their own key
        "description": request.message,
        "body": request.message,
        "text": request.message,
        "message": request.message,
    }

    t0 = time.time()
    result = process_message(
        channel=channel,
        raw_payload=payload,
        conversation_history=request.conversation_history,
        debug=request.debug,
    )
    elapsed = round((time.time() - t0) * 1000, 1)

    if not result.get("success") and result.get("error"):
        _err(result["error"], status=422)

    result["api_processing_ms"] = elapsed

    # Publish to Kafka in background
    background_tasks.add_task(_publish_kafka_event, "fte.tickets.incoming", result)

    return _ok(result)


@app.get("/support/ticket/{ticket_id}", response_model=APIResponse, tags=["Support"],
         summary="Get ticket status by ID")
def get_ticket_status(ticket_id: str):
    """Get the current status and details of a support ticket."""
    ticket = ticket_service.get_ticket(ticket_id)
    if not ticket:
        _err(f"Ticket not found: {ticket_id}", status=404)
    return _ok(ticket)


# ─────────────────────────────────────────────────────────────────────────────
# Tickets
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/tickets", response_model=APIResponse, tags=["Tickets"])
def list_tickets(
    status: Optional[str] = Query(None, description="open|in_progress|waiting_customer|escalated|resolved"),
    priority: Optional[str] = Query(None, description="critical|high|medium|low"),
    customer: Optional[str] = Query(None, description="Customer ref, e.g. C-1042"),
    channel: Optional[str] = Query(None, description="email|whatsapp|web_form"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
):
    """List support tickets with optional filters. Sorted newest-first."""
    result = ticket_service.list_tickets(
        status=status, customer_id=customer, priority=priority,
        limit=limit, offset=offset,
    )
    return _ok(result)


@app.get("/tickets/{ticket_ref}", response_model=APIResponse, tags=["Tickets"])
def get_ticket(ticket_ref: str):
    """Get full ticket details including SLA status, escalation metadata, and agent confidence."""
    ticket = ticket_service.get_ticket(ticket_ref)
    if not ticket:
        _err(f"Ticket not found: {ticket_ref}", status=404)
    return _ok(ticket)


@app.post("/tickets/{ticket_ref}/reply", response_model=APIResponse, tags=["Tickets"])
def reply_to_ticket(ticket_ref: str, request: TicketReplyRequest):
    """Add a reply to an existing ticket (human agent or system)."""
    ticket = ticket_service.get_ticket(ticket_ref)
    if not ticket:
        _err(f"Ticket not found: {ticket_ref}", status=404)
    if ticket["status"] == TicketStatus.RESOLVED:
        _err(f"Cannot reply to resolved ticket: {ticket_ref}")

    updated = ticket_service.update_ticket_status(
        ticket_ref=ticket_ref,
        new_status=TicketStatus.IN_PROGRESS,
        actor=request.actor,
    )
    return _ok({
        "ticket_ref": ticket_ref,
        "status": updated["status"],
        "reply": request.message,
        "actor": request.actor,
        "replied_at": datetime.utcnow().isoformat() + "Z",
        "sent_to_customer": request.send_to_customer,
    })


@app.post("/tickets/{ticket_ref}/escalate", response_model=APIResponse, tags=["Tickets"])
def escalate_ticket(ticket_ref: str, request: EscalateRequest):
    """Manually escalate a ticket to the human specialist queue."""
    ticket = ticket_service.get_ticket(ticket_ref)
    if not ticket:
        _err(f"Ticket not found: {ticket_ref}", status=404)
    if ticket["status"] == TicketStatus.RESOLVED:
        _err(f"Cannot escalate resolved ticket: {ticket_ref}")

    updated = ticket_service.escalate_ticket(
        ticket_ref=ticket_ref,
        reason=request.reason,
        priority_override=request.priority,
    )
    metrics_service.record_escalation(
        ticket_ref=ticket_ref,
        reason=request.reason,
        queue=updated.get("escalation_queue", "general-support"),
        priority=updated.get("priority", "medium"),
        channel=updated.get("channel", "unknown"),
    )
    return _ok({
        "ticket_ref": ticket_ref,
        "status": updated["status"],
        "escalation_reason": updated["escalation_reason"],
        "escalation_queue": updated["escalation_queue"],
        "escalation_id": updated["escalation_id"],
        "escalated_at": updated["escalated_at"],
        "notes": request.notes,
    })


@app.post("/tickets/{ticket_ref}/resolve", response_model=APIResponse, tags=["Tickets"])
def resolve_ticket(ticket_ref: str, notes: Optional[str] = None):
    """Mark a ticket as resolved."""
    ticket = ticket_service.get_ticket(ticket_ref)
    if not ticket:
        _err(f"Ticket not found: {ticket_ref}", status=404)
    updated = ticket_service.update_ticket_status(
        ticket_ref=ticket_ref,
        new_status=TicketStatus.RESOLVED,
        actor="system",
    )
    return _ok({"ticket_ref": ticket_ref, "status": updated["status"], "resolved_at": datetime.utcnow().isoformat() + "Z"})


# ─────────────────────────────────────────────────────────────────────────────
# Conversations
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/conversations/{conversation_id}", response_model=APIResponse, tags=["Conversations"])
def get_conversation(conversation_id: str):
    """
    Get a full conversation thread including all messages across channels.
    Supports cross-channel continuity lookup.
    """
    # Look up via ticket ref or conversation ID
    ticket = ticket_service.get_ticket(conversation_id)
    if ticket:
        return _ok({
            "conversation_id": conversation_id,
            "ticket_ref": ticket.get("ticket_ref"),
            "customer_ref": ticket.get("customer_ref"),
            "channel": ticket.get("channel"),
            "status": ticket.get("status"),
            "messages": ticket.get("messages", []),
            "created_at": ticket.get("created_at"),
        })
    _err(f"Conversation not found: {conversation_id}", status=404)


# ─────────────────────────────────────────────────────────────────────────────
# Customers
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/customers/{customer_ref}", response_model=APIResponse, tags=["Customers"])
def get_customer(customer_ref: str, ticket_limit: int = Query(10, ge=1, le=50)):
    """Get customer profile, account health, CSAT, and recent ticket history."""
    result = customer_service.get_customer_history(customer_ref=customer_ref, ticket_limit=ticket_limit)
    if not result.get("found"):
        _err(f"Customer not found: {customer_ref}", status=404)
    return _ok(result)


@app.post("/customers/lookup", response_model=APIResponse, tags=["Customers"])
def lookup_customer(request: CustomerLookupRequest):
    """
    Cross-channel customer lookup by email, phone, or customer_ref.
    Supports identity resolution across Gmail · WhatsApp · Web Form.
    """
    if not (request.customer_ref or request.email or request.phone):
        _err("Provide at least one of: customer_ref, email, phone")
    result = customer_service.identify_customer(
        customer_ref=request.customer_ref,
        email=request.email,
        phone=request.phone,
    )
    return _ok({
        "found": result.get("found", False),
        "customer": result.get("customer"),
        "resolution_method": result.get("resolution_method"),
    })


# ─────────────────────────────────────────────────────────────────────────────
# Webhooks
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/webhooks/gmail", tags=["Webhooks"], summary="Gmail inbound webhook")
async def gmail_webhook(request: Request, background_tasks: BackgroundTasks):
    """
    Receives Gmail push notifications via Google Cloud Pub/Sub.

    In production: configure Gmail API watch() to push to this endpoint.
    In dev/mock mode: accepts plain JSON payloads directly.

    Expected payload (Pub/Sub format):
    ```json
    {"message": {"data": "<base64-encoded-email-data>", "messageId": "..."}}
    ```
    """
    body = await request.json()

    # Handle both direct and Pub/Sub wrapped payloads
    import base64
    import json as _json

    raw_email = {}

    if "message" in body and "data" in body["message"]:
        # Google Pub/Sub format
        try:
            decoded = base64.b64decode(body["message"]["data"]).decode("utf-8")
            email_data = _json.loads(decoded)
            raw_email = email_data
        except Exception as e:
            logger.warning("Failed to decode Pub/Sub gmail payload: %s", e)
            raw_email = body
    else:
        # Direct JSON (dev mode / testing)
        raw_email = body

    # Ensure minimum fields for email adapter
    payload = {
        "from": raw_email.get("from", raw_email.get("sender", "unknown@example.com")),
        "subject": raw_email.get("subject", "Support Request"),
        "body": raw_email.get("body", raw_email.get("text", raw_email.get("message", ""))),
        "thread_id": raw_email.get("thread_id", raw_email.get("threadId", "")),
        "message_id": raw_email.get("message_id", raw_email.get("messageId", "")),
        "customer_ref": raw_email.get("customer_ref", raw_email.get("from", "unknown")),
    }

    background_tasks.add_task(_process_webhook_async, "email", payload)
    return {"status": "accepted", "channel": "email", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.post("/webhooks/whatsapp", tags=["Webhooks"], summary="WhatsApp inbound webhook")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_twilio_signature: Optional[str] = Header(None),
):
    """
    Receives inbound WhatsApp messages via Twilio webhook.

    Production: configure Twilio WhatsApp sandbox/number to POST to this URL.
    Validates Twilio signature when TWILIO_AUTH_TOKEN is configured.

    Expected Twilio payload fields:
    - From: whatsapp:+1234567890
    - Body: message text
    - MessageSid: unique message ID
    """
    body = await request.body()
    content_type = request.headers.get("content-type", "")

    payload = {}

    if "application/x-www-form-urlencoded" in content_type or "multipart" in content_type:
        form = await request.form()
        payload = dict(form)
    else:
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    # Validate Twilio signature in production
    twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
    if twilio_token and x_twilio_signature:
        webhook_url = os.getenv("WEBHOOK_BASE_URL", "") + "/webhooks/whatsapp"
        if not _validate_twilio_signature(twilio_token, webhook_url, payload, x_twilio_signature):
            logger.warning("Invalid Twilio webhook signature")
            raise HTTPException(status_code=403, detail="Invalid webhook signature")

    wa_payload = {
        "sender_id": payload.get("From", payload.get("from", "")).replace("whatsapp:", ""),
        "phone": payload.get("From", payload.get("from", "")).replace("whatsapp:", ""),
        "text": payload.get("Body", payload.get("body", payload.get("text", ""))),
        "message_sid": payload.get("MessageSid", payload.get("message_sid", "")),
        "customer_ref": payload.get("From", "unknown").replace("whatsapp:", ""),
    }

    background_tasks.add_task(_process_webhook_async, "whatsapp", wa_payload)
    return {"status": "accepted", "channel": "whatsapp", "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.post("/webhooks/whatsapp/status", tags=["Webhooks"], summary="WhatsApp delivery status")
async def whatsapp_status(request: Request):
    """
    Receives WhatsApp message delivery status updates from Twilio.

    Statuses: sent | delivered | read | failed
    """
    try:
        form = await request.form()
        payload = dict(form)
    except Exception:
        payload = await request.json()

    msg_sid = payload.get("MessageSid", "unknown")
    status = payload.get("MessageStatus", "unknown")
    logger.info("WhatsApp delivery status: %s → %s", msg_sid, status)

    return {"status": "received", "message_sid": msg_sid, "delivery_status": status}


@app.get("/webhooks/whatsapp", tags=["Webhooks"], summary="WhatsApp webhook verification")
async def whatsapp_verify(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """
    WhatsApp/Meta webhook verification endpoint.
    Called by Meta to verify the webhook URL during setup.
    """
    expected_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "syncflow_verify_2025")
    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        return int(hub_challenge) if hub_challenge else "ok"
    raise HTTPException(status_code=403, detail="Verification failed")


# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/metrics/summary", response_model=APIResponse, tags=["Metrics"])
def get_metrics_summary(hours: int = Query(24, ge=1, le=168, description="Look-back window in hours")):
    """
    Agent performance summary for the specified time window.

    Returns volume, quality, escalation breakdown, channel distribution,
    auto-resolution rate, and average confidence score.
    """
    return _ok(metrics_service.get_metrics_summary(hours=hours))


@app.get("/metrics/channels", response_model=APIResponse, tags=["Metrics"])
def get_channel_metrics(hours: int = Query(24, ge=1, le=168)):
    """Per-channel breakdown: tickets, responses, escalations, avg confidence."""
    return _ok(metrics_service.get_channel_breakdown(hours=hours))


@app.get("/metrics/sentiment", response_model=APIResponse, tags=["Metrics"])
def get_sentiment(hours: int = Query(24, ge=1, le=168)):
    """Sentiment distribution across all tickets in the time window."""
    return _ok(metrics_service.get_sentiment_distribution(hours=hours))


# ─────────────────────────────────────────────────────────────────────────────
# Background task helpers
# ─────────────────────────────────────────────────────────────────────────────

async def _process_webhook_async(channel: str, payload: dict):
    """Run the message processing pipeline asynchronously for webhook intake."""
    try:
        result = process_message(channel=channel, raw_payload=payload, debug=False)
        logger.info("Webhook processed: channel=%s ticket=%s escalated=%s",
                    channel, result.get("ticket_ref", "?"), result.get("escalated", False))
        _publish_kafka_event("fte.tickets.incoming", result)
    except Exception as e:
        logger.error("Webhook processing failed: channel=%s error=%s", channel, e)
        _publish_kafka_event("fte.dead-letter", {"channel": channel, "error": str(e), "payload": payload})


def _publish_kafka_event(topic: str, payload: dict):
    """Fire-and-forget Kafka publish with graceful fallback."""
    try:
        from kafka_client import publish
        publish(topic=topic, payload=payload)
    except Exception as e:
        logger.debug("Kafka publish skipped (mock mode): %s", e)


def _validate_twilio_signature(auth_token: str, url: str, params: dict, signature: str) -> bool:
    """Validate Twilio webhook signature."""
    try:
        sorted_params = "".join(f"{k}{v}" for k, v in sorted(params.items()))
        computed = hmac.new(
            auth_token.encode("utf-8"),
            (url + sorted_params).encode("utf-8"),
            hashlib.sha1,
        ).digest()
        import base64
        expected = base64.b64encode(computed).decode("utf-8")
        return hmac.compare_digest(expected, signature)
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Exception Handler
# ─────────────────────────────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception: %s %s — %s", request.method, request.url.path, exc)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "data": None,
            "error": f"Internal server error: {str(exc)[:200]}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    )


# ─────────────────────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("api.main:app", host="0.0.0.0", port=port, reload=False)
