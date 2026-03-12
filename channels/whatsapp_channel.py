"""
WhatsApp Channel Adapter – Stage 2
NovaSync Technologies / SyncFlow Customer Success Digital FTE

Handles inbound Meta WhatsApp Business API webhooks and outbound message dispatch.

Responsibilities:
  - Parse WhatsApp Cloud API webhook payloads into normalized format
  - Extract sender phone number (MSISDN) and message text
  - Strip WhatsApp-specific formatting artifacts
  - Send replies via WhatsApp Business API (simulated)
  - Handle message status callbacks (delivered, read)

Production upgrade: replace simulated dispatch with actual Meta Cloud API calls.
"""

import re
from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# WhatsApp Message Type Support
# ---------------------------------------------------------------------------

SUPPORTED_MESSAGE_TYPES = {"text", "interactive", "button"}


# ---------------------------------------------------------------------------
# Normalize Inbound Message
# ---------------------------------------------------------------------------

def normalize(raw_payload: dict) -> dict:
    """
    Normalize a raw WhatsApp Cloud API webhook payload into a standard MessagePayload.

    Handles the nested Meta webhook structure:
        entry[0].changes[0].value.messages[0]

    Or a simplified dict for internal use:
        {from_number, display_name, text, wamid, timestamp}

    Args:
        raw_payload: WhatsApp Cloud API webhook body OR simplified dict.

    Returns:
        dict — normalized MessagePayload:
          channel:         "whatsapp"
          raw_text:        The cleaned message text
          sender_phone:    WhatsApp phone number (with country code)
          sender_name:     Display name from WhatsApp profile
          external_id:     WhatsApp message ID (WAMID)
          metadata:        Channel-specific extras
          normalized_at:   ISO 8601 timestamp
    """
    # Handle simplified format (used internally and in tests)
    if "from_number" in raw_payload:
        return _normalize_simple(raw_payload)

    # Handle Meta Cloud API webhook format
    try:
        value    = raw_payload["entry"][0]["changes"][0]["value"]
        message  = value["messages"][0]
        contact  = value["contacts"][0]
        msg_type = message.get("type", "text")

        if msg_type not in SUPPORTED_MESSAGE_TYPES:
            # Non-text message (image, audio, etc.) — return placeholder
            return _normalize_non_text(message, contact)

        text     = _extract_text(message, msg_type)
        phone    = message.get("from", "")
        wamid    = message.get("id", "")
        name     = contact.get("profile", {}).get("name", _name_from_phone(phone))
        ts       = message.get("timestamp", "")

    except (KeyError, IndexError):
        # Malformed webhook — best-effort extraction
        text  = raw_payload.get("text", raw_payload.get("body", ""))
        phone = raw_payload.get("from", raw_payload.get("phone", ""))
        name  = raw_payload.get("name", "WhatsApp User")
        wamid = raw_payload.get("id", "")
        ts    = raw_payload.get("timestamp", datetime.utcnow().isoformat())

    clean_text = _clean_whatsapp_text(text)

    return {
        "channel":       "whatsapp",
        "raw_text":      clean_text,
        "sender_phone":  _normalize_phone(phone),
        "sender_name":   name.strip() if name else "WhatsApp User",
        "sender_email":  None,
        "subject":       None,
        "thread_id":     None,  # WhatsApp uses sender phone as thread identifier
        "external_id":   wamid,
        "metadata": {
            "message_type":   msg_type if "msg_type" in dir() else "text",
            "raw_text_length": len(text) if "text" in dir() else 0,
            "has_emoji":       _has_emoji(clean_text),
            "all_caps_ratio":  _caps_ratio(clean_text),
        },
        "normalized_at": datetime.utcnow().isoformat(),
    }


def send_reply(
    to_phone: str,
    body: str,
    ticket_ref: Optional[str] = None,
    reply_to_wamid: Optional[str] = None,
) -> dict:
    """
    Dispatch an outbound WhatsApp message.

    In production: calls Meta Graph API v18+/messages endpoint.
    Current implementation: simulates dispatch with mock WAMID.

    Args:
        to_phone:       Recipient phone number in E.164 format (+14155551234).
        body:           Plain-text message body (max 4096 chars, enforced).
        ticket_ref:     Ticket reference for logging correlation.
        reply_to_wamid: WAMID of the message being replied to (context linking).

    Returns:
        dict — delivery receipt:
          success:          bool
          wamid:            str — WhatsApp message ID
          delivery_status:  "delivered" | "pending" | "failed"
          sent_at:          ISO 8601 timestamp
          error:            str | None
    """
    if not to_phone or not body:
        return _failed_receipt("Missing recipient phone or message body")

    # Enforce WhatsApp's 4096-character limit
    if len(body) > 4096:
        body = body[:4093] + "..."

    # Enforce the 80-word guideline from Stage 1 (channel contract)
    word_count = len(body.split())
    if word_count > 80:
        words = body.split()[:80]
        body  = " ".join(words) + "..."

    wamid = f"wamid.{datetime.utcnow().strftime('%Y%m%d%H%M%S')}{abs(hash(to_phone)) % 10000:04d}"

    # Simulated delivery — in production: requests.post(META_API_URL, ...)
    return {
        "success":         True,
        "wamid":           wamid,
        "delivery_status": "delivered",
        "sent_at":         datetime.utcnow().isoformat(),
        "to_phone":        to_phone,
        "body_preview":    body[:80],
        "word_count":      word_count,
        "gateway":         "Meta Cloud API (simulated)",
        "ticket_ref":      ticket_ref,
        "reply_to_wamid":  reply_to_wamid,
        "error":           None,
    }


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _normalize_simple(payload: dict) -> dict:
    """Handle simplified dict format used in tests and internal pipelines."""
    text  = payload.get("text", "")
    phone = payload.get("from_number", "")
    return {
        "channel":       "whatsapp",
        "raw_text":      _clean_whatsapp_text(text),
        "sender_phone":  _normalize_phone(phone),
        "sender_name":   payload.get("display_name", _name_from_phone(phone)),
        "sender_email":  None,
        "subject":       None,
        "thread_id":     None,
        "external_id":   payload.get("wamid"),
        "metadata": {
            "message_type":   "text",
            "raw_text_length": len(text),
            "has_emoji":       _has_emoji(text),
            "all_caps_ratio":  _caps_ratio(text),
        },
        "normalized_at": payload.get("timestamp", datetime.utcnow().isoformat()),
    }


def _normalize_non_text(message: dict, contact: dict) -> dict:
    """Return a minimal payload for non-text WhatsApp messages."""
    msg_type = message.get("type", "unknown")
    phone    = message.get("from", "")
    name     = contact.get("profile", {}).get("name", "WhatsApp User")
    return {
        "channel":       "whatsapp",
        "raw_text":      f"[{msg_type.upper()} message received — text not available]",
        "sender_phone":  _normalize_phone(phone),
        "sender_name":   name,
        "sender_email":  None,
        "subject":       None,
        "thread_id":     None,
        "external_id":   message.get("id"),
        "metadata":      {"message_type": msg_type, "is_non_text": True},
        "normalized_at": datetime.utcnow().isoformat(),
    }


def _extract_text(message: dict, msg_type: str) -> str:
    """Extract text content from different WhatsApp message types."""
    if msg_type == "text":
        return message.get("text", {}).get("body", "")
    if msg_type == "interactive":
        # Button reply or list selection
        interactive = message.get("interactive", {})
        if "button_reply" in interactive:
            return interactive["button_reply"].get("title", "")
        if "list_reply" in interactive:
            return interactive["list_reply"].get("title", "")
    if msg_type == "button":
        return message.get("button", {}).get("text", "")
    return ""


def _clean_whatsapp_text(text: str) -> str:
    """
    Clean WhatsApp-specific formatting artifacts.
    - Strip WhatsApp bold (*text*) and italic (_text_) markers
    - Normalize excessive whitespace
    """
    text = re.sub(r'\*([^*]+)\*', r'\1', text)  # Bold: *text* → text
    text = re.sub(r'_([^_]+)_', r'\1', text)     # Italic: _text_ → text
    text = re.sub(r'~([^~]+)~', r'\1', text)     # Strikethrough: ~text~ → text
    text = re.sub(r'\s+', ' ', text)             # Normalize whitespace
    return text.strip()


def _normalize_phone(phone: str) -> str:
    """Normalize phone to E.164 format where possible."""
    if not phone:
        return ""
    digits = re.sub(r'\D', '', phone)
    if len(digits) == 10:
        return f"+1{digits}"
    if len(digits) > 10 and not phone.startswith("+"):
        return f"+{digits}"
    return phone if phone.startswith("+") else f"+{digits}"


def _name_from_phone(phone: str) -> str:
    """Generate a placeholder name from a phone number."""
    if not phone:
        return "WhatsApp User"
    return f"User ({phone[-4:]})"


def _has_emoji(text: str) -> bool:
    """Detect if text contains emoji characters."""
    emoji_pattern = re.compile(
        "[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF]+",
        flags=re.UNICODE
    )
    return bool(emoji_pattern.search(text))


def _caps_ratio(text: str) -> float:
    """Compute ratio of uppercase letters to total alpha chars."""
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return 0.0
    return round(sum(1 for c in alpha if c.isupper()) / len(alpha), 2)


def _failed_receipt(reason: str) -> dict:
    return {
        "success":         False,
        "wamid":           None,
        "delivery_status": "failed",
        "sent_at":         datetime.utcnow().isoformat(),
        "gateway":         "Meta Cloud API (simulated)",
        "error":           reason,
    }
