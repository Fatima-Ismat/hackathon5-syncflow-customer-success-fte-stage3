"""
agent/models.py
NovaSync Technologies / SyncFlow — Customer Success Digital FTE
Stage 3: Pydantic v2 data models for the agent I/O pipeline.

All models use strict field validation and include rich docstrings so the
auto-generated OpenAPI schema at /docs is self-documenting.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Generic type variable for the ToolResult wrapper
# ---------------------------------------------------------------------------
T = TypeVar("T")


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ChannelType(str, Enum):
    """
    Supported inbound communication channels.

    Values are lowercase strings that map 1-to-1 to the channel adapters
    in the ``channels/`` package.
    """

    email = "email"
    whatsapp = "whatsapp"
    web_form = "web_form"


class Priority(str, Enum):
    """Ticket priority levels — from lowest to highest urgency."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


# ---------------------------------------------------------------------------
# Sentiment
# ---------------------------------------------------------------------------


class SentimentScore(BaseModel):
    """
    Structured sentiment analysis result produced by the ``analyze_sentiment``
    tool.

    Scores are normalised to the ``[0.0, 1.0]`` range.  ``overall`` is a
    human-readable label that summarises the dominant emotional signal.
    """

    anger: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Anger intensity score: 0 = calm, 1 = extremely angry.",
    )
    frustration: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Frustration intensity score: 0 = satisfied, 1 = highly frustrated.",
    )
    urgency: bool = Field(
        default=False,
        description="True when the customer signals time-critical urgency.",
    )
    overall: str = Field(
        default="neutral",
        description=(
            "Dominant sentiment label: "
            "``positive`` | ``neutral`` | ``frustrated`` | ``angry``."
        ),
    )

    @field_validator("overall")
    @classmethod
    def _valid_overall(cls, v: str) -> str:
        allowed = {"positive", "neutral", "frustrated", "angry"}
        if v not in allowed:
            raise ValueError(f"overall must be one of {allowed}; got {v!r}")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "anger": 0.15,
                "frustration": 0.45,
                "urgency": True,
                "overall": "frustrated",
            }
        }
    }


# ---------------------------------------------------------------------------
# Customer context
# ---------------------------------------------------------------------------


class CustomerContext(BaseModel):
    """
    Enriched customer profile injected into the agent's context window.

    Populated by ``get_customer_history`` tool call before the main
    response-generation step.
    """

    customer_ref: str = Field(
        ...,
        description="Unique CRM customer reference (e.g. ``C-1042``).",
    )
    name: str = Field(
        default="",
        description="Customer's full display name.",
    )
    email: Optional[str] = Field(
        default=None,
        description="Customer's primary email address.",
    )
    plan: str = Field(
        default="starter",
        description="Active subscription plan: starter | growth | business | enterprise.",
    )
    account_health: str = Field(
        default="good",
        description="CRM health label: good | at_risk | churning.",
    )
    recent_tickets: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Up to 5 most recent support tickets for this customer.",
    )
    is_vip: bool = Field(
        default=False,
        description="True for high-value / enterprise accounts that get SLA priority.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "customer_ref": "C-6229",
                "name": "Lena Hoffmann",
                "email": "lena@acme.io",
                "plan": "business",
                "account_health": "good",
                "recent_tickets": [],
                "is_vip": True,
            }
        }
    }


# ---------------------------------------------------------------------------
# Agent I/O
# ---------------------------------------------------------------------------


class AgentInput(BaseModel):
    """
    Normalised input payload for the :class:`~agent.CustomerSuccessAgent`.

    Constructed by the message worker after channel normalisation and
    customer identification.
    """

    channel: ChannelType = Field(
        ...,
        description="The channel this message arrived on.",
    )
    customer_ref: str = Field(
        ...,
        min_length=1,
        description="Customer CRM reference string.",
    )
    message: str = Field(
        ...,
        min_length=1,
        description="Raw inbound message text from the customer.",
    )
    customer_context: Optional[CustomerContext] = Field(
        default=None,
        description=(
            "Pre-fetched customer context.  If ``None`` the agent will call "
            "``get_customer_history`` to fetch it during orchestration."
        ),
    )
    conversation_history: list[dict[str, Any]] = Field(
        default_factory=list,
        description=(
            "Prior conversation turns.  Each element: "
            "``{role: 'user'|'assistant', content: str}``."
        ),
    )
    topic: Optional[str] = Field(
        default=None,
        description="Optional pre-classified topic hint from the channel adapter.",
    )

    @field_validator("channel", mode="before")
    @classmethod
    def _normalise_channel(cls, v: Any) -> str:
        """Accept ``'web'`` as an alias for ``'web_form'``."""
        if v == "web":
            return "web_form"
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "channel": "web_form",
                "customer_ref": "C-1042",
                "message": "I cannot reset my password — the link isn't arriving.",
                "conversation_history": [],
            }
        }
    }


class AgentOutput(BaseModel):
    """
    Structured response produced by :class:`~agent.CustomerSuccessAgent`.

    Every field is always populated so downstream consumers never have to
    guard against missing keys.
    """

    response: str = Field(
        ...,
        description="Formatted reply to send to the customer (channel-appropriate).",
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="KB match confidence: 0 = no match, 1 = exact match.",
    )
    escalation_needed: bool = Field(
        default=False,
        description="True when the ticket must be routed to a human agent.",
    )
    escalation_reason: Optional[str] = Field(
        default=None,
        description="Machine-readable reason code for escalation, if applicable.",
    )
    kb_section: Optional[str] = Field(
        default=None,
        description="Knowledge base section that provided the answer, if any.",
    )
    sentiment: SentimentScore = Field(
        default_factory=SentimentScore,
        description="Full sentiment analysis result.",
    )
    suggested_priority: str = Field(
        default="low",
        description="Recommended ticket priority: low | medium | high | critical.",
    )
    processing_time_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Wall-clock time taken to produce this response, in milliseconds.",
    )
    tools_used: list[str] = Field(
        default_factory=list,
        description="Names of tools invoked during this agent run, in call order.",
    )
    ticket_ref: Optional[str] = Field(
        default=None,
        description="CRM ticket reference created for this interaction.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "response": "Hi Marcus,\n\nHere's how to reset your password...",
                "confidence": 0.82,
                "escalation_needed": False,
                "escalation_reason": None,
                "kb_section": "Password & Security -> Password Reset",
                "sentiment": {
                    "anger": 0.0,
                    "frustration": 0.1,
                    "urgency": False,
                    "overall": "neutral",
                },
                "suggested_priority": "low",
                "processing_time_ms": 142.5,
                "tools_used": [
                    "analyze_sentiment",
                    "get_customer_history",
                    "search_knowledge_base",
                    "create_ticket",
                ],
                "ticket_ref": "TKT-20260311-4821",
            }
        }
    }


# ---------------------------------------------------------------------------
# Generic tool result wrapper
# ---------------------------------------------------------------------------


class ToolResult(BaseModel, Generic[T]):
    """
    Generic wrapper returned by every tool function.

    Provides a consistent envelope so the agent orchestrator can handle
    tool errors uniformly without inspecting each tool's return type.
    """

    success: bool = Field(
        ...,
        description="True if the tool completed without errors.",
    )
    tool_name: str = Field(
        ...,
        description="Name of the tool that produced this result.",
    )
    data: Optional[T] = Field(
        default=None,
        description="Tool-specific payload on success.",
    )
    error: Optional[str] = Field(
        default=None,
        description="Human-readable error message on failure.",
    )
    duration_ms: float = Field(
        default=0.0,
        ge=0.0,
        description="Execution time of the tool call in milliseconds.",
    )

    @model_validator(mode="after")
    def _check_consistency(self) -> "ToolResult[T]":
        if self.success and self.data is None and self.error is not None:
            raise ValueError("Successful ToolResult must not carry an error message.")
        if not self.success and self.error is None:
            raise ValueError("Failed ToolResult must carry an error message.")
        return self

    model_config = {
        "json_schema_extra": {
            "example": {
                "success": True,
                "tool_name": "search_knowledge_base",
                "data": {
                    "found": True,
                    "section": "Password & Security -> Password Reset",
                    "answer": "To reset your password...",
                    "confidence": 0.82,
                    "keywords_matched": ["password", "reset"],
                },
                "error": None,
                "duration_ms": 3.2,
            }
        }
    }
