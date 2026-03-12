"""
database/queries.py
SyncFlow Customer Success Digital FTE — Stage 3

SQLAlchemy query helpers for all CRM operations.
These wrap the ORM models with common business-logic queries.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_, desc

logger = logging.getLogger("syncflow.queries")


# ─────────────────────────────────────────────────────────────────────────────
# Customer Queries
# ─────────────────────────────────────────────────────────────────────────────

def get_customer_by_ref(db: Session, customer_ref: str) -> Optional[Any]:
    """Look up customer by their CRM reference (C-XXXX)."""
    try:
        from database.models import Customer
        return db.query(Customer).filter(Customer.customer_ref == customer_ref).first()
    except Exception as e:
        logger.error("get_customer_by_ref error: %s", e)
        return None


def get_customer_by_email(db: Session, email: str) -> Optional[Any]:
    """Look up customer by email address."""
    try:
        from database.models import Customer, CustomerIdentifier
        return (
            db.query(Customer)
            .join(CustomerIdentifier, Customer.id == CustomerIdentifier.customer_id)
            .filter(
                and_(
                    CustomerIdentifier.identifier_type == "email",
                    CustomerIdentifier.identifier_value == email.lower(),
                )
            )
            .first()
        )
    except Exception as e:
        logger.error("get_customer_by_email error: %s", e)
        return None


def get_customer_by_phone(db: Session, phone: str) -> Optional[Any]:
    """Look up customer by phone number (used for WhatsApp identity)."""
    try:
        from database.models import Customer, CustomerIdentifier
        clean_phone = phone.replace("+", "").replace("-", "").replace(" ", "")
        return (
            db.query(Customer)
            .join(CustomerIdentifier, Customer.id == CustomerIdentifier.customer_id)
            .filter(
                and_(
                    CustomerIdentifier.identifier_type.in_(["phone", "whatsapp"]),
                    CustomerIdentifier.identifier_value.contains(clean_phone[-7:]),
                )
            )
            .first()
        )
    except Exception as e:
        logger.error("get_customer_by_phone error: %s", e)
        return None


def create_customer(db: Session, data: dict) -> Any:
    """Create a new customer record."""
    from database.models import Customer, CustomerIdentifier
    import uuid

    customer = Customer(
        customer_ref=data.get("customer_ref", f"C-{uuid.uuid4().hex[:6].upper()}"),
        name=data.get("name", "Unknown"),
        company=data.get("company"),
        plan=data.get("plan", "starter"),
        is_vip=data.get("is_vip", False),
        account_health=data.get("account_health", "healthy"),
        mrr=data.get("mrr", 0.0),
    )
    db.add(customer)
    db.flush()

    # Add email identifier
    if data.get("email"):
        ident = CustomerIdentifier(
            customer_id=customer.id,
            identifier_type="email",
            identifier_value=data["email"].lower(),
            channel="email",
        )
        db.add(ident)

    # Add phone identifier
    if data.get("phone"):
        ident = CustomerIdentifier(
            customer_id=customer.id,
            identifier_type="phone",
            identifier_value=data["phone"],
            channel="whatsapp",
        )
        db.add(ident)

    db.commit()
    db.refresh(customer)
    return customer


# ─────────────────────────────────────────────────────────────────────────────
# Ticket Queries
# ─────────────────────────────────────────────────────────────────────────────

def get_ticket_by_ref(db: Session, ticket_ref: str) -> Optional[Any]:
    """Get a ticket by its reference (T-XXXXXXXX)."""
    try:
        from database.models import Ticket
        return db.query(Ticket).filter(Ticket.ticket_ref == ticket_ref).first()
    except Exception as e:
        logger.error("get_ticket_by_ref error: %s", e)
        return None


def list_tickets(
    db: Session,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    customer_id: Optional[int] = None,
    channel: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Any]:
    """List tickets with optional filters."""
    try:
        from database.models import Ticket
        q = db.query(Ticket)
        if status:
            q = q.filter(Ticket.status == status)
        if priority:
            q = q.filter(Ticket.priority == priority)
        if customer_id:
            q = q.filter(Ticket.customer_id == customer_id)
        if channel:
            q = q.filter(Ticket.channel == channel)
        return q.order_by(desc(Ticket.created_at)).offset(offset).limit(limit).all()
    except Exception as e:
        logger.error("list_tickets error: %s", e)
        return []


def create_ticket(db: Session, data: dict) -> Any:
    """Create a new support ticket."""
    from database.models import Ticket
    import uuid

    ticket = Ticket(
        ticket_ref=data.get("ticket_ref", f"T-{uuid.uuid4().hex[:8].upper()}"),
        customer_id=data.get("customer_id"),
        subject=data.get("subject", "Support Request"),
        channel=data.get("channel", "web_form"),
        status="open",
        priority=data.get("priority", "medium"),
        sentiment_score=data.get("sentiment_score", 0.0),
        kb_confidence=data.get("kb_confidence", 0.0),
        kb_section=data.get("kb_section"),
        ai_response=data.get("ai_response"),
        escalated=data.get("escalated", False),
        escalation_reason=data.get("escalation_reason"),
        sla_deadline=data.get("sla_deadline"),
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    return ticket


def update_ticket_status(db: Session, ticket_ref: str, new_status: str, actor: str = "system") -> Optional[Any]:
    """Update ticket status."""
    try:
        from database.models import Ticket
        ticket = db.query(Ticket).filter(Ticket.ticket_ref == ticket_ref).first()
        if ticket:
            ticket.status = new_status
            ticket.updated_at = datetime.utcnow()
            if new_status == "resolved":
                ticket.resolved_at = datetime.utcnow()
            db.commit()
            db.refresh(ticket)
        return ticket
    except Exception as e:
        logger.error("update_ticket_status error: %s", e)
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Message Queries
# ─────────────────────────────────────────────────────────────────────────────

def create_message(db: Session, data: dict) -> Any:
    """Store a message (inbound or outbound) in the database."""
    from database.models import Message

    msg = Message(
        ticket_id=data.get("ticket_id"),
        direction=data.get("direction", "inbound"),
        channel=data.get("channel", "web_form"),
        content=data.get("content", ""),
        sender_ref=data.get("sender_ref"),
        channel_message_id=data.get("channel_message_id"),
        sentiment_score=data.get("sentiment_score", 0.0),
        confidence_score=data.get("confidence_score", 0.0),
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


def get_conversation_messages(db: Session, ticket_id: int) -> List[Any]:
    """Get all messages for a ticket conversation."""
    try:
        from database.models import Message
        return (
            db.query(Message)
            .filter(Message.ticket_id == ticket_id)
            .order_by(Message.created_at)
            .all()
        )
    except Exception as e:
        logger.error("get_conversation_messages error: %s", e)
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Knowledge Base Queries
# ─────────────────────────────────────────────────────────────────────────────

def search_knowledge_base_db(db: Session, query: str, limit: int = 3) -> List[Any]:
    """Full-text search against the knowledge base table."""
    try:
        from database.models import KnowledgeBase
        # Simple ILIKE search — in production use pgvector or full-text search
        terms = query.lower().split()
        results = []
        for term in terms[:3]:
            rows = (
                db.query(KnowledgeBase)
                .filter(
                    or_(
                        func.lower(KnowledgeBase.title).contains(term),
                        func.lower(KnowledgeBase.content).contains(term),
                        func.lower(KnowledgeBase.tags).contains(term),
                    )
                )
                .limit(limit)
                .all()
            )
            results.extend(rows)

        # Deduplicate by id
        seen = set()
        unique = []
        for r in results:
            if r.id not in seen:
                seen.add(r.id)
                unique.append(r)

        return unique[:limit]
    except Exception as e:
        logger.error("search_knowledge_base_db error: %s", e)
        return []


def record_kb_usage(db: Session, kb_id: int):
    """Increment the usage counter for a KB article."""
    try:
        from database.models import KnowledgeBase
        kb = db.query(KnowledgeBase).filter(KnowledgeBase.id == kb_id).first()
        if kb:
            kb.usage_count = (kb.usage_count or 0) + 1
            db.commit()
    except Exception as e:
        logger.error("record_kb_usage error: %s", e)


# ─────────────────────────────────────────────────────────────────────────────
# Metrics Queries
# ─────────────────────────────────────────────────────────────────────────────

def get_ticket_metrics(db: Session, since: datetime) -> dict:
    """Aggregate ticket metrics since a given datetime."""
    try:
        from database.models import Ticket
        total = db.query(func.count(Ticket.id)).filter(Ticket.created_at >= since).scalar() or 0
        escalated = db.query(func.count(Ticket.id)).filter(
            and_(Ticket.created_at >= since, Ticket.escalated == True)  # noqa
        ).scalar() or 0
        resolved = db.query(func.count(Ticket.id)).filter(
            and_(Ticket.created_at >= since, Ticket.status == "resolved")
        ).scalar() or 0
        avg_confidence = db.query(func.avg(Ticket.kb_confidence)).filter(
            Ticket.created_at >= since
        ).scalar() or 0.0

        return {
            "total": total,
            "escalated": escalated,
            "resolved": resolved,
            "avg_confidence": round(float(avg_confidence), 3),
            "auto_resolution_rate": round(resolved / max(total, 1), 3),
        }
    except Exception as e:
        logger.error("get_ticket_metrics error: %s", e)
        return {}
