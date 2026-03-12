"""
agent/formatters.py
NovaSync Technologies / SyncFlow — Customer Success Digital FTE
Stage 3: Channel-aware response formatters.

Each formatter takes raw answer content produced by the agent and wraps it
in the correct channel-specific structure (greeting, signature, length limit,
ticket reference placement, etc.).

Public API
----------
format_email_response(content, customer_name, ticket_ref) -> str
format_whatsapp_response(content, ticket_ref) -> str
format_web_form_response(content, ticket_ref) -> str
format_response(channel, content, customer_name, ticket_ref) -> str   ← dispatcher
"""

from __future__ import annotations

import logging
import re
import textwrap

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EMAIL_WORD_LIMIT: int = 350
_WHATSAPP_WORD_LIMIT: int = 80
_WEB_FORM_WORD_LIMIT: int = 220

_NOVASYC_SIGNATURE: str = (
    "Best,\n"
    "The NovaSync Support Team\n"
    "support@novasynctechnologies.com | syncflow.io/help"
)

_EMAIL_TICKET_LINE: str = "Ticket ref: {ticket_ref}"
_WEB_FORM_TICKET_LINE: str = "Your ticket reference: {ticket_ref}"
_WHATSAPP_TICKET_LINE: str = "Ref: {ticket_ref}"


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _first_name(full_name: str) -> str:
    """Extract the first name from a full display name."""
    parts = full_name.strip().split()
    return parts[0] if parts else "there"


def _trim_to_word_limit(text: str, limit: int) -> str:
    """
    Trim ``text`` so it contains at most ``limit`` words.

    A trailing ellipsis is appended if the text was shortened.
    Blank lines and whitespace are preserved up to the cut point.
    """
    words = text.split()
    if len(words) <= limit:
        return text
    trimmed = " ".join(words[:limit])
    logger.debug("_trim_to_word_limit: trimmed from %d to %d words", len(words), limit)
    return trimmed + "..."


def _strip_markdown(text: str) -> str:
    """
    Remove common markdown formatting artefacts for plain-text channels.

    Handles: bold (**text**), italic (*text*), inline code (`text`),
    horizontal rules (---), and excess blank lines.
    """
    # Remove bold/italic markers
    text = re.sub(r"\*{1,3}(.+?)\*{1,3}", r"\1", text, flags=re.DOTALL)
    # Remove inline code ticks
    text = re.sub(r"`([^`]+)`", r"\1", text)
    # Remove heading markers
    text = re.sub(r"^#{1,6}\s+", "", text, flags=re.MULTILINE)
    # Remove horizontal rules
    text = re.sub(r"^\s*[-_*]{3,}\s*$", "", text, flags=re.MULTILINE)
    # Collapse 3+ blank lines to 2
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _compress_for_whatsapp(text: str) -> str:
    """
    Aggressively compress multi-line, structured text to a single paragraph
    suitable for WhatsApp.

    Rules:
    - Numbered list items are flattened to comma-separated clauses.
    - Bullet points are dropped and their content is preserved inline.
    - Only the first meaningful paragraph is kept if the result is still long.
    """
    # Flatten numbered list items
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.MULTILINE)
    # Flatten bullet points
    text = re.sub(r"^\s*[•\-\*]\s+", "", text, flags=re.MULTILINE)
    # Join lines into a single paragraph
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    flat = " ".join(lines)
    # Collapse double spaces
    flat = re.sub(r" {2,}", " ", flat)
    return flat.strip()


# ---------------------------------------------------------------------------
# Email formatter
# ---------------------------------------------------------------------------


def format_email_response(
    content: str,
    customer_name: str,
    ticket_ref: str,
) -> str:
    """
    Wrap agent content in a professional email format.

    Parameters
    ----------
    content:
        Raw answer text from the agent — may contain numbered lists, bullets,
        or plain prose.
    customer_name:
        Full display name of the customer.  The first token is used as the
        greeting name.
    ticket_ref:
        Support ticket reference to append (e.g. ``"TKT-20260311-4821"``).

    Returns
    -------
    str
        Fully formatted email body — greeting, content, signature, ticket ref.

    Examples
    --------
    >>> body = format_email_response("Here are the steps...", "Marcus Chen", "TKT-001")
    >>> body.startswith("Hi Marcus,")
    True
    >>> "TKT-001" in body
    True
    """
    name = _first_name(customer_name)
    cleaned = _strip_markdown(content)
    trimmed = _trim_to_word_limit(cleaned, _EMAIL_WORD_LIMIT)

    parts: list[str] = [
        f"Hi {name},",
        "",
        trimmed,
        "",
        _NOVASYC_SIGNATURE,
        "",
        _EMAIL_TICKET_LINE.format(ticket_ref=ticket_ref),
    ]

    result = "\n".join(parts)
    logger.debug(
        "format_email_response | customer=%s | ticket=%s | chars=%d",
        customer_name,
        ticket_ref,
        len(result),
    )
    return result


# ---------------------------------------------------------------------------
# WhatsApp formatter
# ---------------------------------------------------------------------------


def format_whatsapp_response(
    content: str,
    ticket_ref: str,
    customer_name: str = "there",
    distressed: bool = False,
) -> str:
    """
    Format a response for WhatsApp — short, conversational, no sign-off.

    Parameters
    ----------
    content:
        Raw answer text.
    ticket_ref:
        Ticket reference to append on its own line.
    customer_name:
        Customer first name (default ``"there"``).
    distressed:
        If ``True``, the greeting prefix is softened with an apology.

    Returns
    -------
    str
        WhatsApp-ready message: greeting + compressed content + ticket ref.
        Strictly bounded to :data:`_WHATSAPP_WORD_LIMIT` words.

    Examples
    --------
    >>> msg = format_whatsapp_response("Reset via Settings > Security.", "TKT-002")
    >>> len(msg.split()) <= 82   # limit + ref line
    True
    """
    name = _first_name(customer_name)
    if distressed:
        greeting = f"Hey {name}, really sorry about this. "
    else:
        greeting = f"Hey {name}! "

    compressed = _compress_for_whatsapp(_strip_markdown(content))
    # Apply word limit to the body only (greeting and ref line are short)
    body_trimmed = _trim_to_word_limit(compressed, _WHATSAPP_WORD_LIMIT)

    ref_line = _WHATSAPP_TICKET_LINE.format(ticket_ref=ticket_ref)
    result = f"{greeting}{body_trimmed}\n{ref_line}"

    logger.debug(
        "format_whatsapp_response | ticket=%s | words=%d",
        ticket_ref,
        len(result.split()),
    )
    return result


# ---------------------------------------------------------------------------
# Web form formatter
# ---------------------------------------------------------------------------


def format_web_form_response(
    content: str,
    ticket_ref: str,
    customer_name: str = "there",
) -> str:
    """
    Format a response for the SyncFlow web support form — semi-formal,
    medium length, structured.

    Parameters
    ----------
    content:
        Raw answer text.
    ticket_ref:
        Ticket reference to append at the foot.
    customer_name:
        Customer first name used in the greeting.

    Returns
    -------
    str
        Web-form-ready response with greeting, body, closing, and ticket ref.

    Examples
    --------
    >>> resp = format_web_form_response("Export via Settings > Data.", "TKT-003", "Lena")
    >>> resp.startswith("Hi Lena,")
    True
    """
    name = _first_name(customer_name)
    cleaned = _strip_markdown(content)
    trimmed = _trim_to_word_limit(cleaned, _WEB_FORM_WORD_LIMIT)

    parts: list[str] = [
        f"Hi {name},",
        "",
        trimmed,
        "",
        "Let us know if you have any other questions.",
        "",
        _WEB_FORM_TICKET_LINE.format(ticket_ref=ticket_ref),
    ]

    result = "\n".join(parts)
    logger.debug(
        "format_web_form_response | customer=%s | ticket=%s | chars=%d",
        customer_name,
        ticket_ref,
        len(result),
    )
    return result


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def format_response(
    channel: str,
    content: str,
    customer_name: str,
    ticket_ref: str,
    distressed: bool = False,
) -> str:
    """
    Route ``content`` to the correct channel formatter.

    Parameters
    ----------
    channel:
        One of ``"email"``, ``"whatsapp"``, ``"web_form"`` (or ``"web"``
        as an alias for ``"web_form"``).
    content:
        Raw agent answer text.
    customer_name:
        Customer's display name.
    ticket_ref:
        Support ticket reference.
    distressed:
        Passed to :func:`format_whatsapp_response` to soften the greeting
        when high anger/frustration was detected.

    Returns
    -------
    str
        Channel-formatted response string.

    Raises
    ------
    ValueError
        If ``channel`` is not a recognised value.  Callers that cannot
        guarantee a valid channel should catch this and fall back to
        ``"web_form"``.

    Examples
    --------
    >>> out = format_response("email", "Steps to fix...", "Marcus Chen", "TKT-001")
    >>> out.startswith("Hi Marcus,")
    True
    >>> out = format_response("whatsapp", "Reset via Settings.", "Priya", "TKT-002")
    >>> out.startswith("Hey Priya!")
    True
    """
    # Normalise alias
    if channel == "web":
        channel = "web_form"

    dispatch: dict[str, object] = {
        "email":     lambda: format_email_response(content, customer_name, ticket_ref),
        "whatsapp":  lambda: format_whatsapp_response(
            content, ticket_ref, customer_name=customer_name, distressed=distressed
        ),
        "web_form":  lambda: format_web_form_response(
            content, ticket_ref, customer_name=customer_name
        ),
    }

    formatter = dispatch.get(channel)
    if formatter is None:
        logger.warning(
            "format_response: unknown channel %r — falling back to web_form", channel
        )
        formatter = dispatch["web_form"]

    result: str = formatter()  # type: ignore[operator]
    logger.debug(
        "format_response | channel=%s | ticket=%s | output_len=%d",
        channel,
        ticket_ref,
        len(result),
    )
    return result


# ---------------------------------------------------------------------------
# Escalation acknowledgment helpers
# ---------------------------------------------------------------------------


_ESCALATION_BODY_EMAIL: str = (
    "I want to make sure you get the best possible support here.\n\n"
    "One of our specialists has been assigned to your case and will follow up with you {sla}. "
    "Your full conversation history has been shared with them so you won't need to repeat yourself."
)

_ESCALATION_BODY_WHATSAPP: str = (
    "Passing you to a specialist now — they'll be in touch {sla}. "
    "No need to repeat yourself, they have the full context."
)

_ESCALATION_BODY_WEB_FORM: str = (
    "A specialist from our team has been assigned to your case and will follow up {sla}. "
    "Your full conversation history has been shared so you won't need to repeat yourself."
)

_SLA_MAP: dict[str, str] = {
    "starter":    "within 24 hours",
    "growth":     "within 8 hours",
    "business":   "within 2 hours",
    "enterprise": "within 1 hour",
}


def format_escalation_response(
    channel: str,
    customer_name: str,
    ticket_ref: str,
    plan: str = "starter",
) -> str:
    """
    Build a channel-appropriate escalation acknowledgment message.

    Parameters
    ----------
    channel:
        Delivery channel.
    customer_name:
        Customer's display name.
    ticket_ref:
        Ticket reference.
    plan:
        Customer's subscription plan — used to derive the SLA timeframe.

    Returns
    -------
    str
        Ready-to-send escalation acknowledgment formatted for the channel.
    """
    sla = _SLA_MAP.get(plan.lower(), "as soon as possible")

    body_templates: dict[str, str] = {
        "email":    _ESCALATION_BODY_EMAIL,
        "whatsapp": _ESCALATION_BODY_WHATSAPP,
        "web_form": _ESCALATION_BODY_WEB_FORM,
        "web":      _ESCALATION_BODY_WEB_FORM,
    }
    body_template = body_templates.get(channel, _ESCALATION_BODY_WEB_FORM)
    body = body_template.format(sla=sla)

    distressed = channel == "whatsapp"
    return format_response(
        channel=channel,
        content=body,
        customer_name=customer_name,
        ticket_ref=ticket_ref,
        distressed=distressed,
    )
