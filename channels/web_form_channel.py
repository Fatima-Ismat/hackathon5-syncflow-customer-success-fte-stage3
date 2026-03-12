"""
Web Form Channel Adapter – Stage 2
NovaSync Technologies / SyncFlow Customer Success Digital FTE

Handles inbound web support form submissions and outbound in-widget responses.

Web form submissions are semi-structured: they arrive as JSON payloads with
pre-defined fields (issue_type, description, email, account_id) rather than
free-form text. This gives us cleaner data but requires field extraction.

Responsibilities:
  - Parse structured web form JSON into normalized MessagePayload
  - Pre-extract topic hints from issue_type dropdown values
  - Send responses back via web response API (simulated inline widget)
  - Attach form metadata for context

Production upgrade: replace simulated dispatch with webhook to SyncFlow
web app's real-time response API or email notification fallback.
"""

import re
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Issue Type Mapping (web form dropdown → topic slug)
# ---------------------------------------------------------------------------

ISSUE_TYPE_MAP: dict[str, str] = {
    "billing":                 "billing",
    "billing_question":        "billing",
    "account":                 "account_management",
    "account_access":          "password_reset",
    "login":                   "password_reset",
    "password":                "password_reset",
    "api":                     "api_errors",
    "api_issue":               "api_errors",
    "integration":             "integrations",
    "integration_issue":       "integrations",
    "workflow":                "workflow_trigger",
    "workflow_issue":          "workflow_trigger",
    "team":                    "team_management",
    "team_member":             "team_management",
    "security":                "sso",
    "sso":                     "sso",
    "data":                    "data_export",
    "data_export":             "data_export",
    "other":                   None,
    "general":                 None,
}


# ---------------------------------------------------------------------------
# Normalize Inbound Message
# ---------------------------------------------------------------------------

def normalize(raw_payload: dict) -> dict:
    """
    Normalize a web form submission into a standard MessagePayload.

    Expected raw_payload fields:
        email (str):          Submitter's email address
        name (str):           Submitter's full name
        account_id (str):     Customer account ID if logged in (optional)
        issue_type (str):     Dropdown selection value
        subject (str):        Optional subject field
        description (str):    Free-text description of the issue
        priority_hint (str):  Self-reported urgency: "low"|"medium"|"high" (optional)
        form_id (str):        Form submission UUID (optional)
        submitted_at (str):   ISO 8601 timestamp (optional)

    Returns:
        dict — normalized MessagePayload:
          channel:           "web_form"
          raw_text:          Combined subject + description text
          sender_email:      Extracted email address
          sender_name:       Submitter name
          account_id:        Pre-linked account ID (helps customer identification)
          topic_hint:        Pre-classified topic from issue_type dropdown
          priority_hint:     Self-reported urgency
          external_id:       Form submission ID
          metadata:          Form-specific extras
          normalized_at:     ISO 8601 timestamp
    """
    email      = raw_payload.get("email", "")
    name       = raw_payload.get("name", "")
    account_id = raw_payload.get("account_id")
    issue_type = raw_payload.get("issue_type", "other").lower().replace(" ", "_")
    subject    = raw_payload.get("subject", "")
    description= raw_payload.get("description", raw_payload.get("body", ""))

    # Combine subject and description for richer text matching
    raw_text = _combine_text(subject, description)

    # Map issue_type dropdown to topic slug
    topic_hint = ISSUE_TYPE_MAP.get(issue_type)

    # Extract structured context if description contains form field headers
    extracted = _extract_structured_fields(description)

    # Merge extracted email/account if not at top level
    if not email and extracted.get("email"):
        email = extracted["email"]
    if not account_id and extracted.get("account_id"):
        account_id = extracted["account_id"]

    return {
        "channel":       "web_form",
        "raw_text":      raw_text.strip(),
        "sender_email":  email.lower().strip() if email else None,
        "sender_name":   name.strip() if name else _name_from_email(email),
        "sender_phone":  None,
        "account_id":    account_id,
        "subject":       subject.strip() if subject else None,
        "thread_id":     raw_payload.get("session_id"),
        "external_id":   raw_payload.get("form_id"),
        "topic_hint":    topic_hint,
        "priority_hint": raw_payload.get("priority_hint"),
        "metadata": {
            "issue_type":        issue_type,
            "topic_hint":        topic_hint,
            "has_account_id":    account_id is not None,
            "description_length": len(description),
            "has_structured_fields": bool(extracted),
        },
        "normalized_at": raw_payload.get("submitted_at", datetime.utcnow().isoformat()),
    }


def send_reply(
    session_id: str,
    body: str,
    ticket_ref: Optional[str] = None,
    sender_email: Optional[str] = None,
) -> dict:
    """
    Dispatch an outbound web form response.

    Two delivery modes:
      1. In-widget: instant response displayed in the form widget (session_id present)
      2. Email fallback: sends confirmation email if session has expired

    In production: calls SyncFlow web response API or triggers email notification.

    Args:
        session_id:    Browser session ID for in-widget delivery.
        body:          Response text (already formatted for web_form channel).
        ticket_ref:    Ticket reference for user confirmation.
        sender_email:  Fallback email address if session is unavailable.

    Returns:
        dict — delivery receipt.
    """
    if not session_id and not sender_email:
        return _failed_receipt("No session_id or fallback email provided")

    if not body:
        return _failed_receipt("Response body is empty")

    response_id = f"WFR-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{abs(hash(session_id or sender_email or '')) % 10000:04d}"

    mode = "in_widget" if session_id else "email_fallback"

    return {
        "success":         True,
        "response_id":     response_id,
        "delivery_mode":   mode,
        "delivery_status": "delivered",
        "sent_at":         datetime.utcnow().isoformat(),
        "session_id":      session_id,
        "ticket_ref":      ticket_ref,
        "gateway":         "SyncFlow Web Response API (simulated)",
        "body_preview":    body[:120],
        "error":           None,
    }


def extract_metadata(normalized: dict) -> dict:
    """
    Extract additional metadata from a normalized web form payload for logging.

    Returns a concise metadata dict suitable for ticket tagging.
    """
    tags = []
    meta = normalized.get("metadata", {})

    if normalized.get("topic_hint"):
        tags.append(normalized["topic_hint"])
    if meta.get("has_account_id"):
        tags.append("authenticated")
    if normalized.get("priority_hint") in ("high", "urgent"):
        tags.append("self_reported_urgent")

    return {
        "tags":         tags,
        "topic_hint":   normalized.get("topic_hint"),
        "priority_hint": normalized.get("priority_hint"),
        "account_id":   normalized.get("account_id"),
        "issue_type":   meta.get("issue_type"),
    }


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _combine_text(subject: str, description: str) -> str:
    """Build a single searchable text string from subject + description."""
    parts = []
    if subject and subject.strip():
        parts.append(subject.strip())
    if description and description.strip():
        parts.append(description.strip())
    return "\n\n".join(parts) if parts else ""


def _extract_structured_fields(text: str) -> dict:
    """
    Extract email, account ID, and other structured values from free-text descriptions.
    Handles common web form patterns like "Account: j.whitfield@techbridge.com"
    """
    extracted = {}

    # Email pattern
    email_match = re.search(r'[\w.+-]+@[\w-]+\.[\w.]+', text)
    if email_match:
        extracted["email"] = email_match.group(0)

    # Account ID pattern (C-XXXX or similar)
    account_match = re.search(r'\bC-\d{4,6}\b', text)
    if account_match:
        extracted["account_id"] = account_match.group(0)

    return extracted


def _name_from_email(email: str) -> str:
    """Derive a display name from email address."""
    if not email or "@" not in email:
        return "Support Customer"
    local = email.split("@")[0]
    return " ".join(part.capitalize() for part in re.split(r'[._\-]', local))


def _failed_receipt(reason: str) -> dict:
    return {
        "success":         False,
        "response_id":     None,
        "delivery_mode":   None,
        "delivery_status": "failed",
        "sent_at":         datetime.utcnow().isoformat(),
        "gateway":         "SyncFlow Web Response API (simulated)",
        "error":           reason,
    }
