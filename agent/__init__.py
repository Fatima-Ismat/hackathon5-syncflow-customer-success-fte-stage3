"""
agent/__init__.py
NovaSync Technologies / SyncFlow — Customer Success Digital FTE
Stage 3: OpenAI Agents SDK-compatible production agent package.

This package provides the core AI agent for handling multi-channel
customer support at SyncFlow. It integrates sentiment analysis,
knowledge base search, ticket creation, and escalation routing.

Public API
----------
run(channel, customer_ref, message, conversation_history=None) -> dict
    Top-level convenience wrapper. Identical interface to
    process_customer_message so the existing backend/agent_bridge.py
    can import either without changes.

process_customer_message(...)
    Alias for run() – retained for backwards compatibility with
    backend/agent_bridge.py and workers/message_worker.py.
"""

from __future__ import annotations

import logging
from typing import Any

# ── internal imports ──────────────────────────────────────────────────────────
from .customer_success_agent import (
    CustomerSuccessAgent,
    process_customer_message,
)

__all__: list[str] = [
    "run",
    "process_customer_message",
    "CustomerSuccessAgent",
]

__version__: str = "3.0.0"
__author__: str = "NovaSync Technologies"

logger = logging.getLogger(__name__)


def run(
    channel: str,
    customer_ref: str,
    message: str,
    conversation_history: list[dict[str, Any]] | None = None,
    topic: str | None = None,
) -> dict[str, Any]:
    """
    Top-level entry point for the Customer Success Digital FTE agent.

    Wraps :func:`process_customer_message` with a keyword-argument-only
    interface that is easier to call from tests and the CLI.

    Parameters
    ----------
    channel:
        Delivery channel: ``"email"``, ``"whatsapp"``, or ``"web_form"``.
    customer_ref:
        Customer CRM reference (e.g. ``"C-1042"``) or any unique identifier.
    message:
        Raw inbound message text from the customer.
    conversation_history:
        Optional list of prior conversation turns.  Each element should be
        a dict with at least ``{"role": "user"|"assistant", "content": str}``.
    topic:
        Optional pre-classified topic string (e.g. ``"password_reset"``).
        Useful when the channel adapter has already performed topic routing.

    Returns
    -------
    dict
        Full agent result dict as defined by
        :func:`~agent.customer_success_agent.process_customer_message`.
        Keys include: ``response``, ``ticket_ref``, ``escalated``,
        ``sentiment``, ``confidence``, ``kb_section``,
        ``processing_time_ms``, ``tools_used``.
    """
    logger.debug(
        "agent.run called | channel=%s | customer_ref=%s | msg_len=%d",
        channel,
        customer_ref,
        len(message or ""),
    )
    return process_customer_message(
        channel=channel,
        customer_ref=customer_ref,
        message=message,
        conversation_history=conversation_history,
        topic=topic,
    )
