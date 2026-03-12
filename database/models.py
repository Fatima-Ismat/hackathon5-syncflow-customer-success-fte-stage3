"""
CRM Database Models – Stage 2
NovaSync Technologies / SyncFlow Customer Success Digital FTE

SQLAlchemy ORM models for the Customer Success CRM system.
Designed for PostgreSQL (production). Compatible with SQLite for local dev.

Tables:
  - customers              Core customer identity and plan metadata
  - customer_identifiers   Email, phone, external IDs for lookup
  - conversations          Threaded conversation containers
  - messages               Individual messages within a conversation
  - tickets                Support ticket lifecycle tracking
  - knowledge_base         Searchable product documentation entries
  - agent_metrics          AI agent performance analytics

Usage:
  from database.models import Base, Customer, Ticket
  # In production: bind to a real PostgreSQL engine via DATABASE_URL env var
  # For demo: uses in-memory SQLite
"""

from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index,
    Integer, String, Text, JSON, Enum, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class TicketStatus(str, PyEnum):
    OPEN             = "open"
    IN_PROGRESS      = "in_progress"
    WAITING_CUSTOMER = "waiting_customer"
    ESCALATED        = "escalated"
    RESOLVED         = "resolved"


class TicketPriority(str, PyEnum):
    CRITICAL = "critical"
    HIGH     = "high"
    MEDIUM   = "medium"
    LOW      = "low"


class ChannelType(str, PyEnum):
    EMAIL     = "email"
    WHATSAPP  = "whatsapp"
    WEB_FORM  = "web_form"


class CustomerPlan(str, PyEnum):
    STARTER    = "starter"
    GROWTH     = "growth"
    BUSINESS   = "business"
    ENTERPRISE = "enterprise"


class MessageDirection(str, PyEnum):
    INBOUND  = "inbound"
    OUTBOUND = "outbound"


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------

class Customer(Base):
    """
    Core customer record.
    One customer can have multiple identifiers (email, phone, external CRM ID).
    """
    __tablename__ = "customers"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    customer_ref   = Column(String(20), unique=True, nullable=False, index=True,
                            comment="Human-readable customer ID: C-1042")
    name           = Column(String(255), nullable=False)
    plan           = Column(Enum(CustomerPlan), nullable=False, default=CustomerPlan.STARTER)
    is_vip         = Column(Boolean, nullable=False, default=False)
    account_health = Column(String(50), nullable=False, default="healthy",
                            comment="healthy | at_risk | churned")
    mrr            = Column(Float, nullable=True, comment="Monthly recurring revenue in USD")
    csat_average   = Column(Float, nullable=True, comment="Average CSAT score 1.0–5.0")
    total_tickets  = Column(Integer, nullable=False, default=0)
    open_tickets   = Column(Integer, nullable=False, default=0)
    last_contact   = Column(DateTime, nullable=True)
    account_created = Column(DateTime, nullable=False, default=func.now())
    created_at     = Column(DateTime, nullable=False, default=func.now())
    updated_at     = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    # Relationships
    identifiers   = relationship("CustomerIdentifier", back_populates="customer",
                                  cascade="all, delete-orphan")
    tickets       = relationship("Ticket", back_populates="customer")
    conversations = relationship("Conversation", back_populates="customer")

    def __repr__(self) -> str:
        return f"<Customer {self.customer_ref} ({self.name}) plan={self.plan}>"


# ---------------------------------------------------------------------------
# CustomerIdentifier
# ---------------------------------------------------------------------------

class CustomerIdentifier(Base):
    """
    Multiple lookup identifiers for a single customer.
    Enables identification by email, phone, WhatsApp number, or external CRM ID.
    """
    __tablename__ = "customer_identifiers"
    __table_args__ = (
        UniqueConstraint("identifier_type", "identifier_value", name="uq_identifier"),
        Index("ix_customer_identifiers_value", "identifier_value"),
    )

    id               = Column(Integer, primary_key=True, autoincrement=True)
    customer_id      = Column(Integer, ForeignKey("customers.id", ondelete="CASCADE"),
                              nullable=False)
    identifier_type  = Column(String(50), nullable=False,
                               comment="email | phone | whatsapp | salesforce_id | hubspot_id")
    identifier_value = Column(String(255), nullable=False)
    is_primary       = Column(Boolean, nullable=False, default=False)
    created_at       = Column(DateTime, nullable=False, default=func.now())

    customer = relationship("Customer", back_populates="identifiers")

    def __repr__(self) -> str:
        return f"<CustomerIdentifier {self.identifier_type}={self.identifier_value}>"


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------

class Conversation(Base):
    """
    A threaded conversation container.
    Spans one or more messages across potentially multiple turns.
    Cross-channel continuity is enabled by linking conversations via customer_id.
    """
    __tablename__ = "conversations"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    conversation_ref = Column(String(30), unique=True, nullable=False, index=True,
                               comment="CONV-20260311-1234")
    customer_id     = Column(Integer, ForeignKey("customers.id"), nullable=False)
    channel         = Column(Enum(ChannelType), nullable=False)
    ticket_id       = Column(Integer, ForeignKey("tickets.id"), nullable=True)
    status          = Column(String(30), nullable=False, default="active",
                             comment="active | closed | archived")
    turn_count      = Column(Integer, nullable=False, default=0)
    context_data    = Column(JSON, nullable=True,
                             comment="Arbitrary context: session tokens, form data, etc.")
    started_at      = Column(DateTime, nullable=False, default=func.now())
    last_message_at = Column(DateTime, nullable=True)
    closed_at       = Column(DateTime, nullable=True)

    # Relationships
    customer  = relationship("Customer", back_populates="conversations")
    messages  = relationship("Message", back_populates="conversation",
                              cascade="all, delete-orphan", order_by="Message.created_at")
    ticket    = relationship("Ticket", foreign_keys=[ticket_id])

    def __repr__(self) -> str:
        return f"<Conversation {self.conversation_ref} channel={self.channel} turns={self.turn_count}>"


# ---------------------------------------------------------------------------
# Message
# ---------------------------------------------------------------------------

class Message(Base):
    """
    An individual message within a conversation.
    Can be inbound (from customer) or outbound (AI/human reply).
    Stores sentiment analysis results and agent confidence scores.
    """
    __tablename__ = "messages"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    message_ref     = Column(String(30), unique=True, nullable=False, index=True,
                              comment="MSG-20260311-123456-001")
    conversation_id = Column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"),
                              nullable=False)
    direction       = Column(Enum(MessageDirection), nullable=False)
    content         = Column(Text, nullable=False)
    channel         = Column(Enum(ChannelType), nullable=False)
    sender_id       = Column(String(50), nullable=True,
                              comment="customer_ref for inbound, 'ai_agent'/'human:name' for outbound")

    # Sentiment analysis (Stage 2 enhancement)
    sentiment_label      = Column(String(30), nullable=True,
                                  comment="positive | neutral | frustrated | angry")
    sentiment_score      = Column(Float, nullable=True, comment="Composite sentiment score 0.0–1.0")
    anger_score          = Column(Float, nullable=True)
    frustration_score    = Column(Float, nullable=True)
    urgency_detected     = Column(Boolean, nullable=True)
    profanity_detected   = Column(Boolean, nullable=True)

    # Agent metadata (outbound only)
    agent_confidence     = Column(Float, nullable=True, comment="KB confidence score 0.0–1.0")
    kb_section_used      = Column(String(100), nullable=True)
    processing_time_ms   = Column(Integer, nullable=True)

    # Delivery tracking
    delivery_status      = Column(String(30), nullable=True,
                                  comment="delivered | pending | failed")
    external_message_id  = Column(String(100), nullable=True,
                                  comment="Channel-specific message ID (WhatsApp WAMID, Gmail ID)")

    created_at  = Column(DateTime, nullable=False, default=func.now())
    delivered_at = Column(DateTime, nullable=True)

    conversation = relationship("Conversation", back_populates="messages")

    __table_args__ = (
        Index("ix_messages_conversation_id", "conversation_id"),
        Index("ix_messages_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Message {self.message_ref} dir={self.direction} sentiment={self.sentiment_label}>"


# ---------------------------------------------------------------------------
# Ticket
# ---------------------------------------------------------------------------

class Ticket(Base):
    """
    Support ticket with full lifecycle tracking.

    States: OPEN → IN_PROGRESS → WAITING_CUSTOMER | ESCALATED → RESOLVED

    Includes:
      - SLA deadline and breach tracking
      - Tagging system for classification
      - Escalation routing metadata
      - Agent assignment tracking
    """
    __tablename__ = "tickets"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    ticket_ref  = Column(String(30), unique=True, nullable=False, index=True,
                          comment="TKT-20260311-1234")
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    channel     = Column(Enum(ChannelType), nullable=False)
    status      = Column(Enum(TicketStatus), nullable=False, default=TicketStatus.OPEN)
    priority    = Column(Enum(TicketPriority), nullable=False, default=TicketPriority.MEDIUM)

    subject         = Column(String(500), nullable=True)
    topic           = Column(String(100), nullable=True,
                             comment="Classified topic: password_reset | billing_question | ...")
    tags            = Column(JSON, nullable=True, comment="List of string tags: ['billing','vip']")
    assigned_to     = Column(String(100), nullable=False, default="ai_agent",
                             comment="'ai_agent' or queue name or human agent ID")

    # Escalation metadata
    escalation_reason  = Column(String(100), nullable=True)
    escalation_queue   = Column(String(100), nullable=True)
    escalation_id      = Column(String(50), nullable=True)
    escalated_at       = Column(DateTime, nullable=True)

    # SLA tracking
    sla_deadline       = Column(DateTime, nullable=True)
    sla_breached       = Column(Boolean, nullable=False, default=False)
    resolution_time_s  = Column(Integer, nullable=True,
                                comment="Seconds from creation to resolution")

    # Agent performance
    agent_confidence   = Column(Float, nullable=True,
                                comment="Final KB confidence score used for response")
    sentiment_at_open  = Column(String(30), nullable=True)
    kb_used            = Column(Boolean, nullable=False, default=False)

    created_at  = Column(DateTime, nullable=False, default=func.now())
    updated_at  = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())
    resolved_at = Column(DateTime, nullable=True)

    # Relationships
    customer      = relationship("Customer", back_populates="tickets")
    conversations = relationship("Conversation", foreign_keys="Conversation.ticket_id")

    __table_args__ = (
        Index("ix_tickets_customer_id", "customer_id"),
        Index("ix_tickets_status", "status"),
        Index("ix_tickets_priority", "priority"),
        Index("ix_tickets_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<Ticket {self.ticket_ref} status={self.status} priority={self.priority}>"


# ---------------------------------------------------------------------------
# KnowledgeBase
# ---------------------------------------------------------------------------

class KnowledgeBase(Base):
    """
    Structured knowledge base entries for AI-assisted support.
    Each entry covers one topic with keywords, content, and usage tracking.

    In Stage 3: replace keyword list with vector embeddings for semantic search.
    """
    __tablename__ = "knowledge_base"

    id           = Column(Integer, primary_key=True, autoincrement=True)
    section_id   = Column(String(100), unique=True, nullable=False, index=True,
                           comment="Slug: password_reset | api_rate_limits | billing")
    title        = Column(String(500), nullable=False)
    content      = Column(Text, nullable=False)
    keywords     = Column(JSON, nullable=False, comment="List of keyword strings for matching")
    tags         = Column(JSON, nullable=True, comment="Category tags")
    channel_hints = Column(JSON, nullable=True,
                            comment="Channel-specific content variants: {email: '...', whatsapp: '...'}")

    # Usage analytics
    times_retrieved    = Column(Integer, nullable=False, default=0)
    times_led_to_resolve = Column(Integer, nullable=False, default=0)
    resolution_rate    = Column(Float, nullable=True,
                                comment="Computed: times_led_to_resolve / times_retrieved")
    avg_confidence     = Column(Float, nullable=True)

    is_active    = Column(Boolean, nullable=False, default=True)
    created_at   = Column(DateTime, nullable=False, default=func.now())
    updated_at   = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    def __repr__(self) -> str:
        return f"<KnowledgeBase {self.section_id}>"


# ---------------------------------------------------------------------------
# AgentMetrics
# ---------------------------------------------------------------------------

class AgentMetrics(Base):
    """
    Daily/hourly performance metrics for the AI Customer Success Agent.
    Used for monitoring, reporting, and SLA compliance dashboards.
    """
    __tablename__ = "agent_metrics"

    id                   = Column(Integer, primary_key=True, autoincrement=True)
    metric_date          = Column(DateTime, nullable=False, index=True,
                                  comment="Start of the measurement window")
    window_hours         = Column(Integer, nullable=False, default=24,
                                  comment="Window size in hours: 1 (hourly) or 24 (daily)")

    # Volume
    tickets_created      = Column(Integer, nullable=False, default=0)
    messages_processed   = Column(Integer, nullable=False, default=0)
    responses_generated  = Column(Integer, nullable=False, default=0)

    # Outcomes
    escalations          = Column(Integer, nullable=False, default=0)
    resolutions          = Column(Integer, nullable=False, default=0)
    sla_breaches         = Column(Integer, nullable=False, default=0)

    # Quality
    avg_resolution_time_s = Column(Float, nullable=True,
                                    comment="Average ticket resolution time in seconds")
    avg_agent_confidence  = Column(Float, nullable=True,
                                    comment="Average KB confidence score across resolved tickets")
    avg_sentiment_score   = Column(Float, nullable=True,
                                    comment="Average inbound sentiment score (lower = more negative)")

    # Channel breakdown
    channel_usage        = Column(JSON, nullable=True,
                                  comment="{email: N, whatsapp: N, web_form: N}")

    # Escalation breakdown
    escalation_reasons   = Column(JSON, nullable=True,
                                  comment="{reason: count, ...}")

    created_at = Column(DateTime, nullable=False, default=func.now())

    __table_args__ = (
        Index("ix_agent_metrics_date", "metric_date"),
    )

    def __repr__(self) -> str:
        return (
            f"<AgentMetrics {self.metric_date.date()} "
            f"tickets={self.tickets_created} escalations={self.escalations}>"
        )
