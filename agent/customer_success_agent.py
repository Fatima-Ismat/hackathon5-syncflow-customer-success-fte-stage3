"""
agent/customer_success_agent.py
NovaSync Technologies / SyncFlow — Customer Success Digital FTE
Stage 3: Production agent using the OpenAI Agents SDK (with direct fallback).

Architecture
------------
The agent tries to use the OpenAI Agents SDK (``openai-agents`` package) for
autonomous LLM-driven tool calling.  If the SDK or the OpenAI API key is
unavailable, it falls back to a deterministic direct-orchestration path that
calls the same tool functions in a fixed order and composes the response
without an LLM call.  This ensures the agent always produces a complete,
valid ``AgentOutput`` regardless of the deployment environment.

Escalation rules (applied in both paths)
-----------------------------------------
• anger_score > 0.70              → senior-support      (HIGH)
• frustration_score > 0.80        → senior-support      (HIGH)
• mentions "refund" / "money back" → billing-team        (HIGH)
• mentions "lawsuit"/"legal"/"attorney" → legal-team     (CRITICAL)
• mentions "security breach"/"hacked" → security-team   (CRITICAL)
• KB confidence < 0.30            → technical-support   (MEDIUM)
• "talk to human"/"speak to agent" → general-support
• pricing / contract negotiation  → sales-team

Public API
----------
CustomerSuccessAgent        — class
process_customer_message()  — module-level function (backwards-compat)
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any, Optional

# ---------------------------------------------------------------------------
# OpenAI Agents SDK — optional import
# ---------------------------------------------------------------------------

try:
    from agents import Agent, Runner  # type: ignore[import]
    _AGENTS_SDK_AVAILABLE = True
    logging.getLogger(__name__).info(
        "customer_success_agent: OpenAI Agents SDK available — SDK path enabled"
    )
except ImportError:
    _AGENTS_SDK_AVAILABLE = False
    logging.getLogger(__name__).info(
        "customer_success_agent: OpenAI Agents SDK not installed — using direct orchestration"
    )

# ---------------------------------------------------------------------------
# Internal imports
# ---------------------------------------------------------------------------

from .models import (
    AgentInput,
    AgentOutput,
    ChannelType,
    CustomerContext,
    SentimentScore,
)
from .prompts import get_channel_prompt, get_escalation_prompt
from .formatters import format_response, format_escalation_response
from .tools import (
    ALL_TOOLS,
    # Use _impl_ variants for direct orchestration to avoid FunctionTool wrapping
    _impl_analyze_sentiment as analyze_sentiment,
    _impl_create_ticket as create_ticket,
    _impl_escalate_to_human as escalate_to_human,
    _impl_get_customer_history as get_customer_history,
    _impl_search_knowledge_base as search_knowledge_base,
    _impl_update_ticket_status as update_ticket_status,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Escalation rules — thresholds
# ---------------------------------------------------------------------------

_ANGER_ESCALATION_THRESHOLD: float = 0.70
_FRUSTRATION_ESCALATION_THRESHOLD: float = 0.80
_KB_CONFIDENCE_THRESHOLD: float = 0.30

# Regex patterns for message-level escalation triggers
_LEGAL_PATTERNS: list[str] = [
    r"\blawsuit\b", r"\blawyer\b", r"\battorney\b",
    r"\blegal action\b", r"\bsue\b", r"\blitigate\b",
    r"\bcourt\b", r"\bregulatory\b",
]
_SECURITY_PATTERNS: list[str] = [
    r"\bhacked\b", r"\bsecurity breach\b", r"\bdata breach\b",
    r"\bunauthorized access\b", r"\baccount compromise\b",
    r"\bsomeone else logged in\b",
]
_REFUND_PATTERNS: list[str] = [
    r"\brefund\b", r"\bmoney back\b", r"\bchargeback\b",
    r"\bdispute charge\b", r"\breverse payment\b",
]
_TALK_TO_HUMAN_PATTERNS: list[str] = [
    r"\btalk to (a |an )?(human|person|agent|representative)\b",
    r"\bspeak to (a |an )?(human|person|agent|representative)\b",
    r"\breal person\b", r"\became a human\b",
    r"\bescalate( this)?\b", r"\bhuman agent\b",
]
_PRICING_PATTERNS: list[str] = [
    r"\bpricing negotiation\b", r"\bcontract (terms|negotiation)\b",
    r"\brenewal deal\b", r"\bcustom plan\b", r"\bdiscount\b",
    r"\benterprise pricing\b",
]

# Priority rank for comparison
_PRIORITY_RANK: dict[str, int] = {
    "critical": 4, "high": 3, "medium": 2, "low": 1,
}


def _max_priority(a: str, b: str) -> str:
    return a if _PRIORITY_RANK.get(a, 0) >= _PRIORITY_RANK.get(b, 0) else b


# ---------------------------------------------------------------------------
# CustomerSuccessAgent class
# ---------------------------------------------------------------------------


class CustomerSuccessAgent:
    """
    Production Customer Success AI agent for SyncFlow / NovaSync Technologies.

    Supports two execution paths:

    1. **SDK path** (when ``openai-agents`` is installed and
       ``OPENAI_API_KEY`` is set): delegates to ``Runner.run()`` with
       the full tool list and channel-aware system prompt.

    2. **Direct path** (always available): deterministic orchestration
       that calls tools in a fixed order and composes a response using
       KB content + channel formatters — no LLM call required.

    Usage
    -----
    >>> import asyncio
    >>> agent = CustomerSuccessAgent()
    >>> result = asyncio.run(agent.run(agent_input))
    >>> print(result.response)
    """

    def __init__(self) -> None:
        self._sdk_agent: Optional[Any] = None
        logger.info(
            "CustomerSuccessAgent initialised | sdk_available=%s",
            _AGENTS_SDK_AVAILABLE,
        )

    def _get_or_create_sdk_agent(self, channel: str) -> Any:
        """
        Lazily create (or recreate) the SDK Agent with the right channel prompt.

        The SDK Agent is channel-specific because the system prompt encodes
        channel tone and formatting rules.
        """
        if not _AGENTS_SDK_AVAILABLE:
            return None

        prompt = get_channel_prompt(channel)
        try:
            sdk_agent = Agent(
                name="SyncFlow-CustomerSuccess-FTE",
                instructions=prompt,
                tools=ALL_TOOLS,
            )
            logger.debug("SDK Agent created for channel=%s", channel)
            return sdk_agent
        except Exception as exc:
            logger.warning(
                "Failed to create SDK Agent: %s — falling back to direct path", exc
            )
            return None

    async def run(self, agent_input: AgentInput) -> AgentOutput:
        """
        Process an inbound customer message and return a structured response.

        Parameters
        ----------
        agent_input:
            Normalised input payload (channel, customer_ref, message, etc.).

        Returns
        -------
        AgentOutput
            Complete response including formatted text, sentiment, ticket ref,
            confidence, and escalation metadata.
        """
        start_ns = time.perf_counter_ns()
        channel_str = agent_input.channel.value
        logger.info(
            "CustomerSuccessAgent.run | channel=%s | customer_ref=%s | msg_len=%d",
            channel_str,
            agent_input.customer_ref,
            len(agent_input.message),
        )

        # -----------------------------------------------------------------
        # Try SDK path first
        # -----------------------------------------------------------------
        if _AGENTS_SDK_AVAILABLE and os.environ.get("OPENAI_API_KEY"):
            try:
                result = await self._run_sdk(agent_input)
                elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
                result.processing_time_ms = round(elapsed_ms, 2)
                logger.info(
                    "SDK path completed | ticket=%s | escalated=%s | time=%.1f ms",
                    result.ticket_ref,
                    result.escalation_needed,
                    result.processing_time_ms,
                )
                return result
            except Exception as exc:
                logger.warning(
                    "SDK path failed (%s) — falling back to direct orchestration", exc
                )

        # -----------------------------------------------------------------
        # Fallback: direct orchestration
        # -----------------------------------------------------------------
        result = self._orchestrate_direct(agent_input)
        elapsed_ms = (time.perf_counter_ns() - start_ns) / 1_000_000
        result.processing_time_ms = round(elapsed_ms, 2)
        logger.info(
            "Direct path completed | ticket=%s | escalated=%s | time=%.1f ms",
            result.ticket_ref,
            result.escalation_needed,
            result.processing_time_ms,
        )
        return result

    # ------------------------------------------------------------------
    # SDK execution path
    # ------------------------------------------------------------------

    async def _run_sdk(self, agent_input: AgentInput) -> AgentOutput:
        """Delegate to the OpenAI Agents SDK Runner."""
        channel_str = agent_input.channel.value
        sdk_agent = self._get_or_create_sdk_agent(channel_str)
        if sdk_agent is None:
            raise RuntimeError("SDK agent could not be created")

        # Build a rich context message for the LLM
        context_lines: list[str] = [
            f"CHANNEL: {channel_str}",
            f"CUSTOMER_REF: {agent_input.customer_ref}",
        ]
        if agent_input.customer_context:
            ctx = agent_input.customer_context
            context_lines.append(
                f"CUSTOMER_NAME: {ctx.name} | PLAN: {ctx.plan} | "
                f"VIP: {ctx.is_vip} | HEALTH: {ctx.account_health}"
            )
        if agent_input.topic:
            context_lines.append(f"TOPIC_HINT: {agent_input.topic}")
        if agent_input.conversation_history:
            context_lines.append(
                f"PRIOR_TURNS: {len(agent_input.conversation_history)}"
            )

        system_context = "\n".join(context_lines)
        full_message = f"[CONTEXT]\n{system_context}\n\n[CUSTOMER MESSAGE]\n{agent_input.message}"

        sdk_result = await Runner.run(sdk_agent, full_message)
        raw_output: str = sdk_result.final_output or ""

        # Extract tool call metadata from SDK run
        tools_used: list[str] = []
        try:
            for step in sdk_result.new_messages:
                for item in getattr(step, "content", []):
                    if hasattr(item, "type") and item.type == "tool_use":
                        tools_used.append(item.name)
        except Exception:
            pass  # Metadata extraction is best-effort

        # We still run our own sentiment + ticket tools to populate AgentOutput fields
        sentiment_raw = analyze_sentiment(agent_input.message)
        history_raw = get_customer_history(agent_input.customer_ref)
        kb_raw = search_knowledge_base(agent_input.message, channel_str)

        customer_data = history_raw.get("customer", {})
        plan = customer_data.get("plan", "starter")

        ticket_raw = create_ticket(
            customer_ref=agent_input.customer_ref,
            subject=_generate_subject(agent_input.message, agent_input.topic),
            channel=channel_str,
            priority=_derive_priority(sentiment_raw, kb_raw.get("confidence", 0.0)),
            message=agent_input.message,
        )
        ticket_ref: str = ticket_raw["ticket_ref"]

        escalation_needed, escalation_reason = self._should_escalate(
            sentiment=sentiment_raw,
            confidence=kb_raw.get("confidence", 0.0),
            message=agent_input.message,
            topic=agent_input.topic,
        )

        if escalation_needed:
            escalate_to_human(
                ticket_ref=ticket_ref,
                reason=escalation_reason or "unspecified",
                priority=ticket_raw["priority"],
                customer_ref=agent_input.customer_ref,
                notes=f"SDK agent escalation — {escalation_reason}",
            )
            if "escalate_to_human" not in tools_used:
                tools_used.append("escalate_to_human")

        if "analyze_sentiment" not in tools_used:
            tools_used.insert(0, "analyze_sentiment")

        return AgentOutput(
            response=raw_output,
            confidence=kb_raw.get("confidence", 0.0),
            escalation_needed=escalation_needed,
            escalation_reason=escalation_reason,
            kb_section=kb_raw.get("section") or None,
            sentiment=SentimentScore(
                anger=sentiment_raw["anger"],
                frustration=sentiment_raw["frustration"],
                urgency=sentiment_raw["urgency"],
                overall=sentiment_raw["overall"],
            ),
            suggested_priority=_derive_priority(
                sentiment_raw, kb_raw.get("confidence", 0.0)
            ),
            tools_used=tools_used,
            ticket_ref=ticket_ref,
        )

    # ------------------------------------------------------------------
    # Direct orchestration path (fallback)
    # ------------------------------------------------------------------

    def _orchestrate_direct(self, agent_input: AgentInput) -> AgentOutput:
        """
        Deterministic tool orchestration without an LLM call.

        Calls tools in order, applies escalation rules, and composes
        a channel-formatted response from KB content.
        """
        tools_used: list[str] = []
        channel_str = agent_input.channel.value

        # ── Step 1: Sentiment analysis ──────────────────────────────────
        logger.debug("direct | step=analyze_sentiment")
        sentiment_raw = analyze_sentiment(agent_input.message)
        tools_used.append("analyze_sentiment")
        logger.debug(
            "direct | sentiment=%s anger=%.2f frustration=%.2f urgency=%s",
            sentiment_raw["overall"],
            sentiment_raw["anger"],
            sentiment_raw["frustration"],
            sentiment_raw["urgency"],
        )

        # ── Step 2: Customer history ────────────────────────────────────
        logger.debug("direct | step=get_customer_history")
        history_raw = get_customer_history(agent_input.customer_ref)
        tools_used.append("get_customer_history")
        customer_data = history_raw.get("customer", {})
        customer_name: str = customer_data.get("name", "")
        plan: str = customer_data.get("plan", "starter")
        is_vip: bool = customer_data.get("is_vip", False)

        # ── Step 3: Knowledge base search ──────────────────────────────
        logger.debug("direct | step=search_knowledge_base")
        kb_raw = search_knowledge_base(agent_input.message, channel_str)
        tools_used.append("search_knowledge_base")
        kb_confidence: float = kb_raw.get("confidence", 0.0)
        kb_found: bool = kb_raw.get("found", False)
        kb_answer: str = kb_raw.get("answer", "")
        kb_section: Optional[str] = kb_raw.get("section") or None

        # ── Step 4: Escalation decision ────────────────────────────────
        escalation_needed, escalation_reason = self._should_escalate(
            sentiment=sentiment_raw,
            confidence=kb_confidence,
            message=agent_input.message,
            topic=agent_input.topic,
            is_vip=is_vip,
            conversation_turns=len(agent_input.conversation_history),
        )
        logger.debug(
            "direct | escalation_needed=%s reason=%s", escalation_needed, escalation_reason
        )

        # ── Step 5: Create ticket ───────────────────────────────────────
        logger.debug("direct | step=create_ticket")
        priority = _derive_priority(
            sentiment_raw,
            kb_confidence,
            escalation_reason=escalation_reason,
            is_vip=is_vip,
            plan=plan,
        )
        ticket_raw = create_ticket(
            customer_ref=agent_input.customer_ref,
            subject=_generate_subject(agent_input.message, agent_input.topic),
            channel=channel_str,
            priority=priority,
            message=agent_input.message,
        )
        tools_used.append("create_ticket")
        ticket_ref: str = ticket_raw["ticket_ref"]

        # ── Step 6: Compose response ────────────────────────────────────
        if escalation_needed:
            # Escalation acknowledgment — do not attempt to resolve
            response_text = format_escalation_response(
                channel=channel_str,
                customer_name=customer_name,
                ticket_ref=ticket_ref,
                plan=plan,
            )
            # Mark KB section as None since we didn't use it for resolution
            kb_section = None
            logger.debug("direct | composed escalation acknowledgment")
        elif kb_found and kb_answer:
            # Resolve from KB
            response_text = format_response(
                channel=channel_str,
                content=kb_answer,
                customer_name=customer_name,
                ticket_ref=ticket_ref,
                distressed=sentiment_raw["overall"] in ("frustrated", "angry"),
            )
            logger.debug("direct | composed KB resolution | section=%s", kb_section)
        else:
            # Low confidence — compose clarification request
            clarification = (
                "Thank you for reaching out. To make sure we give you the most accurate "
                "answer, could you provide a bit more detail about the issue? For example, "
                "any error messages you're seeing or the steps you've already tried would help.\n\n"
                "If this is urgent, our support team is also available at "
                "support@novasynctechnologies.com."
            )
            response_text = format_response(
                channel=channel_str,
                content=clarification,
                customer_name=customer_name,
                ticket_ref=ticket_ref,
            )
            # Low confidence but not an escalation — keep ticket open
            logger.debug("direct | composed clarification request (low KB confidence)")

        # ── Step 7: Escalate to human queue if needed ───────────────────
        if escalation_needed:
            logger.debug("direct | step=escalate_to_human | reason=%s", escalation_reason)
            escalate_to_human(
                ticket_ref=ticket_ref,
                reason=escalation_reason or "unspecified",
                priority=priority,
                customer_ref=agent_input.customer_ref,
                notes=(
                    f"Auto-escalated by AI agent. Sentiment: {sentiment_raw['overall']}. "
                    f"KB confidence: {kb_confidence:.2f}."
                ),
            )
            tools_used.append("escalate_to_human")

        # ── Step 8: Update ticket status on resolution ──────────────────
        if not escalation_needed and (kb_found or kb_confidence > 0.0):
            logger.debug("direct | step=update_ticket_status -> resolved")
            update_ticket_status(
                ticket_ref=ticket_ref,
                new_status="resolved",
                notes="Resolved by AI agent via KB match.",
            )
            tools_used.append("update_ticket_status")

        # ── Assemble output ─────────────────────────────────────────────
        return AgentOutput(
            response=response_text,
            confidence=kb_confidence,
            escalation_needed=escalation_needed,
            escalation_reason=escalation_reason,
            kb_section=kb_section,
            sentiment=SentimentScore(
                anger=sentiment_raw["anger"],
                frustration=sentiment_raw["frustration"],
                urgency=sentiment_raw["urgency"],
                overall=sentiment_raw["overall"],
            ),
            suggested_priority=priority,
            tools_used=tools_used,
            ticket_ref=ticket_ref,
        )

    # ------------------------------------------------------------------
    # Escalation decision logic
    # ------------------------------------------------------------------

    def _should_escalate(
        self,
        sentiment: dict[str, Any],
        confidence: float,
        message: str,
        topic: Optional[str] = None,
        is_vip: bool = False,
        conversation_turns: int = 0,
    ) -> tuple[bool, Optional[str]]:
        """
        Apply escalation rules and return ``(escalate: bool, reason: str | None)``.

        Rules are evaluated in priority order — the first matching rule wins.

        Parameters
        ----------
        sentiment:
            Output from :func:`~agent.tools.analyze_sentiment`.
        confidence:
            KB search confidence (0.0–1.0).
        message:
            Raw customer message text.
        topic:
            Pre-classified topic string, if available.
        is_vip:
            True for VIP / enterprise customers.
        conversation_turns:
            Number of prior conversation turns.

        Returns
        -------
        tuple[bool, str | None]
            ``(True, reason_code)`` if escalation is warranted,
            ``(False, None)`` otherwise.
        """
        msg_lower = message.lower()

        # --- Tier 1: Immediate critical escalations ---

        if any(re.search(p, msg_lower) for p in _LEGAL_PATTERNS):
            logger.debug("_should_escalate | legal_threat detected")
            return True, "legal_threat"

        if any(re.search(p, msg_lower) for p in _SECURITY_PATTERNS):
            logger.debug("_should_escalate | security_incident detected")
            return True, "security_incident"

        if any(re.search(p, msg_lower) for p in _REFUND_PATTERNS):
            logger.debug("_should_escalate | refund_request detected")
            return True, "refund_request"

        # --- Tier 2: Sentiment-based escalations ---

        if sentiment.get("profanity"):
            logger.debug("_should_escalate | profanity_detected")
            return True, "profanity_detected"

        if sentiment.get("anger", 0.0) > _ANGER_ESCALATION_THRESHOLD:
            logger.debug(
                "_should_escalate | high_anger_score=%.2f", sentiment["anger"]
            )
            return True, "high_anger_score"

        if sentiment.get("frustration", 0.0) > _FRUSTRATION_ESCALATION_THRESHOLD:
            logger.debug(
                "_should_escalate | high_frustration_score=%.2f",
                sentiment["frustration"],
            )
            return True, "persistent_frustration"

        # --- Tier 3: Explicit escalation requests ---

        if any(re.search(p, msg_lower) for p in _TALK_TO_HUMAN_PATTERNS):
            logger.debug("_should_escalate | explicit_escalation_request")
            return True, "explicit_escalation_request"

        # --- Tier 4: Knowledge base confidence ---

        if confidence < _KB_CONFIDENCE_THRESHOLD:
            logger.debug(
                "_should_escalate | low_kb_confidence=%.2f", confidence
            )
            return True, "low_kb_confidence"

        # --- Tier 5: Pricing / sales signals ---

        if any(re.search(p, msg_lower) for p in _PRICING_PATTERNS):
            logger.debug("_should_escalate | pricing_negotiation detected")
            return True, "pricing_negotiation"

        # --- Tier 6: Conversation-length & VIP rules ---

        if conversation_turns >= 4:
            logger.debug("_should_escalate | unresolved_after_multiple_turns=%d", conversation_turns)
            return True, "unresolved_after_multiple_turns"

        if is_vip and sentiment.get("overall") in ("frustrated", "angry"):
            logger.debug("_should_escalate | vip_customer_negative_sentiment")
            return True, "vip_customer_negative_sentiment"

        if is_vip and conversation_turns >= 2:
            logger.debug("_should_escalate | vip_unresolved turns=%d", conversation_turns)
            return True, "vip_unresolved"

        # --- No escalation ---
        return False, None


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _generate_subject(message: str, topic: Optional[str] = None) -> str:
    """Generate a concise ticket subject line from the message or topic."""
    _TOPIC_SUBJECTS: dict[str, str] = {
        "password_reset":       "Password Reset Assistance",
        "2fa_issue":            "Two-Factor Authentication Issue",
        "api_rate_limit":       "API Rate Limit — Plan Review Needed",
        "api_authentication":   "API Authentication Error (401/403)",
        "billing_question":     "Billing Enquiry",
        "refund_request":       "Refund Request",
        "integration_oauth":    "Integration OAuth Failure",
        "workflow_not_triggering": "Workflow Trigger Troubleshooting",
        "webhook_issue":        "Webhook Duplicate Events",
        "sso_issue":            "SSO Configuration Issue",
        "data_export":          "Data Export Request",
        "team_management":      "Team Member Management",
        "workspace_issue":      "Workspace Configuration",
        "legal_threat":         "URGENT — Legal Matter",
        "security_incident":    "URGENT — Security Incident",
        "account_compromise":   "URGENT — Account Security",
        "cancellation_churn_risk": "Cancellation / Churn Risk",
        "pricing_negotiation":  "Pricing Negotiation Request",
        "enterprise_renewal":   "Enterprise Renewal Discussion",
    }

    if topic and topic in _TOPIC_SUBJECTS:
        return _TOPIC_SUBJECTS[topic]

    # Derive from message text: take the first 80 characters, stop at sentence end
    first_sentence = re.split(r"[.!?\n]", message.strip())[0]
    trimmed = first_sentence.strip()[:80]
    return trimmed if trimmed else "Customer Support Request"


def _derive_priority(
    sentiment: dict[str, Any],
    confidence: float,
    escalation_reason: Optional[str] = None,
    is_vip: bool = False,
    plan: str = "starter",
) -> str:
    """
    Map sentiment and KB confidence signals to a ticket priority string.

    Returns one of: ``"critical"`` | ``"high"`` | ``"medium"`` | ``"low"``.
    """
    priority = "low"

    # Sentiment-driven
    if sentiment.get("anger", 0.0) > _ANGER_ESCALATION_THRESHOLD:
        priority = _max_priority(priority, "high")
    if sentiment.get("frustration", 0.0) > _FRUSTRATION_ESCALATION_THRESHOLD:
        priority = _max_priority(priority, "high")
    if sentiment.get("urgency"):
        priority = _max_priority(priority, "medium")

    # KB confidence floor
    if confidence < _KB_CONFIDENCE_THRESHOLD:
        priority = _max_priority(priority, "medium")

    # Escalation reason overrides
    if escalation_reason in ("legal_threat", "security_incident", "account_compromise"):
        priority = "critical"
    elif escalation_reason in ("refund_request", "high_anger_score",
                                "vip_customer_negative_sentiment"):
        priority = _max_priority(priority, "high")

    # VIP / plan floor rules
    if is_vip and sentiment.get("overall") in ("frustrated", "angry"):
        priority = _max_priority(priority, "high")
    if plan == "enterprise" and sentiment.get("urgency"):
        priority = _max_priority(priority, "high")

    return priority


# ---------------------------------------------------------------------------
# Module-level process_customer_message() — backwards-compatible entry point
# ---------------------------------------------------------------------------


def process_customer_message(
    channel: str,
    customer_ref: str,
    message: str,
    conversation_history: Optional[list[dict[str, Any]]] = None,
    topic: Optional[str] = None,
    customer_id: Optional[str] = None,  # Stage 1 alias
) -> dict[str, Any]:
    """
    Synchronous, module-level wrapper for the ``CustomerSuccessAgent``.

    Provides backward compatibility with ``backend/agent_bridge.py`` which
    imports ``process_customer_message`` from ``customer_success_agent``
    using the Stage 1 positional parameter names.

    The function runs the async agent in a new event loop so it works
    correctly from both sync and async callers.

    Parameters
    ----------
    channel:
        Delivery channel: ``"email"``, ``"whatsapp"``, or ``"web_form"``.
    customer_ref:
        Customer CRM reference.  Falls back to ``customer_id`` if provided
        (Stage 1 compatibility alias).
    message:
        Raw inbound customer message.
    conversation_history:
        Optional list of prior conversation dicts.
    topic:
        Optional pre-classified topic hint.
    customer_id:
        Alias for ``customer_ref`` (Stage 1 compatibility).

    Returns
    -------
    dict
        Keys match the ``agent_bridge.py`` expectations:
          ``response``, ``should_escalate``, ``escalation_reason``,
          ``priority``, ``ticket_id``, ``ticket_ref``, ``sentiment``,
          ``anger_score``, ``frustration_score``, ``urgency_detected``,
          ``kb_confidence``, ``kb_used``, ``kb_section``,
          ``processing_time_ms``, ``tools_used``, ``channel``.
    """
    import asyncio

    # Stage 1 alias resolution
    ref = customer_ref or customer_id or "GUEST"
    if channel == "web":
        channel = "web_form"

    logger.info(
        "process_customer_message | channel=%s | customer_ref=%s | msg_len=%d",
        channel, ref, len(message or ""),
    )

    agent_input = AgentInput(
        channel=channel,  # type: ignore[arg-type]
        customer_ref=ref,
        message=message or "",
        conversation_history=conversation_history or [],
        topic=topic,
    )

    agent = CustomerSuccessAgent()

    # Run in a new event loop (sync wrapper)
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If called from within an async context (e.g. pytest-asyncio)
            # use asyncio.ensure_future and run synchronously via nest_asyncio
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, agent.run(agent_input))
                output: AgentOutput = future.result(timeout=60)
        else:
            output = loop.run_until_complete(agent.run(agent_input))
    except RuntimeError:
        # No event loop — create one
        output = asyncio.run(agent.run(agent_input))

    # Map AgentOutput to the flat dict interface expected by agent_bridge.py
    return {
        # Core response
        "response":             output.response,
        "subject_line":         _derive_subject_line(agent_input.channel.value, topic),
        # Ticket
        "ticket_id":            output.ticket_ref,   # Stage 1 key
        "ticket_ref":           output.ticket_ref,   # Stage 3 key
        # Escalation
        "should_escalate":      output.escalation_needed,
        "escalation_reason":    output.escalation_reason,
        # Priority
        "priority":             output.suggested_priority,
        # Sentiment (flat keys for agent_bridge.py)
        "sentiment":            output.sentiment.overall,
        "anger_score":          output.sentiment.anger,
        "frustration_score":    output.sentiment.frustration,
        "urgency_detected":     output.sentiment.urgency,
        # KB
        "kb_confidence":        output.confidence,
        "kb_used":              output.confidence >= _KB_CONFIDENCE_THRESHOLD,
        "kb_section":           output.kb_section,
        # Meta
        "processing_time_ms":   output.processing_time_ms,
        "tools_used":           output.tools_used,
        "channel":              agent_input.channel.value,
        "timestamp":            _now_iso(),
        "agent_version":        "stage3",
    }


def _derive_subject_line(channel: str, topic: Optional[str]) -> Optional[str]:
    """Return an email subject line only for the email channel."""
    if channel != "email":
        return None
    _TOPIC_SUBJECTS: dict[str, str] = {
        "password_reset":    "Re: Password Reset Assistance",
        "billing_question":  "Re: Billing Enquiry",
        "api_rate_limit":    "Re: API Rate Limit — Next Steps",
        "api_authentication": "Re: API Authentication Issue",
        "sso_issue":         "Re: SSO Configuration",
        "2fa_issue":         "Re: Two-Factor Authentication Help",
        "refund_request":    "Re: Refund Request",
        "legal_threat":      "Re: Your Support Request — Connecting You With Our Team",
        "security_incident": "Re: Account Security — Urgent",
    }
    return _TOPIC_SUBJECTS.get(topic or "", "Re: Your SyncFlow Support Request")


def _now_iso() -> str:
    """Return the current UTC time as an ISO-8601 string."""
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()
