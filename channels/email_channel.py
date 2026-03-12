"""
Email Channel Adapter – Stage 2
NovaSync Technologies / SyncFlow Customer Success Digital FTE

Handles inbound Gmail / SMTP email messages and outbound email dispatch.

Responsibilities:
  - Parse raw email payloads into normalized MessagePayload format
  - Extract sender metadata (email address, subject, body)
  - Send formatted reply emails via simulated gateway
  - Attach thread metadata for conversation continuity

Production upgrade: replace simulated dispatch with Gmail API / SendGrid calls.
"""

import re
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# Normalized Message Format (shared across all channel adapters)
# ---------------------------------------------------------------------------

def normalize(raw_payload: dict) -> dict:
    """
    Normalize a raw inbound email payload into a standard MessagePayload.

    Expected raw_payload fields:
        from_email (str):    Sender's email address
        from_name (str):     Sender's display name (optional)
        subject (str):       Email subject line
        body (str):          Plain-text email body
        thread_id (str):     Gmail thread ID for conversation continuity (optional)
        message_id (str):    External Gmail message ID (optional)
        received_at (str):   ISO 8601 timestamp (optional, defaults to now)

    Returns:
        dict — normalized MessagePayload:
          channel:           "email"
          raw_text:          Cleaned body text
          sender_email:      Extracted email address
          sender_name:       Sender display name
          subject:           Email subject
          thread_id:         Thread reference for conversation linking
          external_id:       Gmail message ID
          metadata:          Dict of channel-specific extras
          normalized_at:     ISO 8601 timestamp
    """
    raw_body   = raw_payload.get("body", "")
    subject    = raw_payload.get("subject", "")
    from_email = raw_payload.get("from_email", "")
    from_name  = raw_payload.get("from_name", "")

    # Strip email signatures (lines starting with -- or common sign-off patterns)
    clean_body = _strip_signature(raw_body)

    # Extract email from malformed "Name <email>" format if needed
    if not from_email and "from_raw" in raw_payload:
        from_email, from_name = _parse_from_header(raw_payload["from_raw"])

    return {
        "channel":        "email",
        "raw_text":       clean_body.strip(),
        "sender_email":   from_email.lower().strip() if from_email else None,
        "sender_name":    from_name.strip() if from_name else _name_from_email(from_email),
        "subject":        subject.strip(),
        "thread_id":      raw_payload.get("thread_id"),
        "external_id":    raw_payload.get("message_id"),
        "metadata": {
            "original_subject": subject,
            "raw_body_length":  len(raw_body),
            "has_signature":    _has_signature(raw_body),
            "is_reply":         subject.lower().startswith("re:"),
        },
        "normalized_at":  raw_payload.get("received_at", datetime.utcnow().isoformat()),
    }


def send_reply(
    to_email: str,
    to_name: str,
    subject: str,
    body: str,
    thread_id: Optional[str] = None,
    ticket_ref: Optional[str] = None,
) -> dict:
    """
    Dispatch an outbound email reply.

    In production: calls Gmail API or SendGrid transactional email API.
    Current implementation: simulates dispatch and returns a mock delivery receipt.

    Args:
        to_email:    Recipient email address.
        to_name:     Recipient display name.
        subject:     Email subject line (should start with "Re:" for replies).
        body:        Plain-text email body (already formatted for email channel).
        thread_id:   Gmail thread ID to maintain conversation threading.
        ticket_ref:  Ticket reference to embed in custom headers.

    Returns:
        dict — delivery receipt:
          success:          bool
          message_id:       str — simulated Gmail message ID
          delivery_status:  "delivered" | "failed"
          sent_at:          ISO 8601 timestamp
          gateway:          str — which gateway was used
          error:            str | None
    """
    if not to_email or not body:
        return _failed_receipt("Missing recipient email or body")

    message_id = f"email-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{hash(to_email) % 10000:04d}"

    # Simulated delivery — in production: gmail_client.send(...)
    return {
        "success":         True,
        "message_id":      message_id,
        "delivery_status": "delivered",
        "sent_at":         datetime.utcnow().isoformat(),
        "gateway":         "Gmail API (simulated)",
        "to_email":        to_email,
        "subject":         subject,
        "thread_id":       thread_id,
        "ticket_ref":      ticket_ref,
        "error":           None,
    }


def format_subject(topic: Optional[str] = None, is_escalation: bool = False) -> str:
    """Generate an appropriate email subject line from topic and escalation status."""
    if is_escalation:
        return "Re: Your Support Request – Connecting You With Our Team"

    topic_map = {
        "password_reset":          "Re: Password Reset Assistance",
        "two_factor_auth":         "Re: Two-Factor Authentication Help",
        "billing":                 "Re: Billing Inquiry",
        "api_errors":              "Re: API Authentication Issue",
        "integrations":            "Re: Integration OAuth Issue",
        "oauth_token_expiry":      "Re: Integration Reconnection Needed",
        "workflow_trigger":        "Re: Workflow Trigger Troubleshooting",
        "webhooks":                "Re: Webhook Configuration",
        "sso":                     "Re: Single Sign-On Setup",
        "data_export":             "Re: Data Export Instructions",
        "team_management":         "Re: Team Member Management",
        "workspaces":              "Re: Workspace Configuration",
        "account_compromise":      "Re: Account Security – Urgent",
        "legal_threat":            "Re: Your Support Request",
        "refund_request":          "Re: Billing Inquiry",
        "pricing_negotiation":     "Re: Plan & Pricing Discussion",
    }
    return topic_map.get(topic or "", "Re: Your SyncFlow Support Request")


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _strip_signature(body: str) -> str:
    """Remove email signatures from message body."""
    lines = body.splitlines()
    clean_lines = []
    for line in lines:
        stripped = line.strip()
        # Common signature separators
        if stripped in ("--", "---", "___", "—") or stripped.startswith("Sent from my "):
            break
        # Common sign-off patterns
        if re.match(r'^(best|regards|thanks|cheers|sincerely|warm regards)[,\s]*$', stripped, re.IGNORECASE):
            break
        clean_lines.append(line)
    return "\n".join(clean_lines)


def _has_signature(body: str) -> bool:
    """Detect whether body contains an email signature."""
    sig_patterns = [r'^--\s*$', r'^Best[,\s]', r'^Regards[,\s]', r'^Thanks[,\s]',
                    r'Sent from my iPhone', r'Sent from my Samsung']
    for line in body.splitlines():
        for pattern in sig_patterns:
            if re.match(pattern, line.strip(), re.IGNORECASE):
                return True
    return False


def _parse_from_header(raw: str) -> tuple[str, str]:
    """Parse 'Display Name <email@domain.com>' format."""
    match = re.match(r'^(.*?)\s*<([^>]+)>\s*$', raw.strip())
    if match:
        return match.group(2).strip(), match.group(1).strip().strip('"')
    # Fallback: raw is just an email
    return raw.strip(), ""


def _name_from_email(email: str) -> str:
    """Derive a display name from an email address as a last resort."""
    if not email or "@" not in email:
        return "Valued Customer"
    local = email.split("@")[0]
    return " ".join(part.capitalize() for part in re.split(r'[._\-]', local))


def _failed_receipt(reason: str) -> dict:
    return {
        "success":         False,
        "message_id":      None,
        "delivery_status": "failed",
        "sent_at":         datetime.utcnow().isoformat(),
        "gateway":         "Gmail API (simulated)",
        "error":           reason,
    }
