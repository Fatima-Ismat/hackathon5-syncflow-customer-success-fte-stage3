"""
Customer Service – Stage 2
NovaSync Technologies / SyncFlow Customer Success Digital FTE

Handles customer identification, creation, and history retrieval.

Customer identification uses three strategies:
  1. Direct customer_ref lookup (C-1042)
  2. Identifier-based lookup (email address, phone number, WhatsApp number)
  3. Create-new fallback for unrecognized contacts

Functions:
    identify_customer()       Multi-strategy customer lookup
    create_customer()         Register a new customer
    get_customer_history()    Full profile + ticket history
    update_customer_stats()   Increment ticket counts, update last_contact

Storage: In-memory dict store (production: replace with SQLAlchemy session).
"""

from datetime import datetime
from typing import Optional


# ---------------------------------------------------------------------------
# In-Memory Stores (replace with DB session in production)
# ---------------------------------------------------------------------------

# Primary customer store: customer_ref → customer dict
_CUSTOMER_STORE: dict[str, dict] = {
    "C-1042": {
        "customer_ref":   "C-1042",
        "name":           "Marcus Chen",
        "plan":           "growth",
        "is_vip":         False,
        "account_health": "healthy",
        "mrr":            99.00,
        "csat_average":   4.6,
        "total_tickets":  3,
        "open_tickets":   0,
        "last_contact":   "2024-11-12",
        "account_created": "2024-03-15",
        "recent_tickets": [
            {"ticket_ref": "TKT-20240901-2211", "topic": "billing_question",      "status": "resolved", "date": "2024-09-01"},
            {"ticket_ref": "TKT-20241112-3301", "topic": "integration_oauth_error","status": "resolved", "date": "2024-11-12"},
        ],
        "created_at": "2024-03-15T00:00:00",
        "updated_at": "2024-11-12T00:00:00",
    },
    "C-2817": {
        "customer_ref":   "C-2817",
        "name":           "Priya Nair",
        "plan":           "starter",
        "is_vip":         False,
        "account_health": "healthy",
        "mrr":            29.00,
        "csat_average":   None,
        "total_tickets":  1,
        "open_tickets":   1,
        "last_contact":   "2026-03-09",
        "account_created": "2025-01-10",
        "recent_tickets": [],
        "created_at": "2025-01-10T00:00:00",
        "updated_at": "2026-03-09T00:00:00",
    },
    "C-3301": {
        "customer_ref":   "C-3301",
        "name":           "James Whitfield",
        "plan":           "business",
        "is_vip":         False,
        "account_health": "healthy",
        "mrr":            299.00,
        "csat_average":   4.2,
        "total_tickets":  8,
        "open_tickets":   0,
        "last_contact":   "2026-01-01",
        "account_created": "2023-07-22",
        "recent_tickets": [
            {"ticket_ref": "TKT-20260101-0091", "topic": "billing_upgrade_confusion", "status": "resolved", "date": "2026-01-01"},
        ],
        "created_at": "2023-07-22T00:00:00",
        "updated_at": "2026-01-01T00:00:00",
    },
    "C-4451": {
        "customer_ref":   "C-4451",
        "name":           "Sofia Reyes",
        "plan":           "growth",
        "is_vip":         False,
        "account_health": "at_risk",
        "mrr":            99.00,
        "csat_average":   3.8,
        "total_tickets":  5,
        "open_tickets":   0,
        "last_contact":   "2026-02-15",
        "account_created": "2025-06-01",
        "recent_tickets": [
            {"ticket_ref": "TKT-20260201-1122", "topic": "api_rate_limit", "status": "resolved", "date": "2026-02-01"},
            {"ticket_ref": "TKT-20260215-2233", "topic": "api_rate_limit", "status": "resolved", "date": "2026-02-15"},
        ],
        "created_at": "2025-06-01T00:00:00",
        "updated_at": "2026-02-15T00:00:00",
    },
    "C-6229": {
        "customer_ref":   "C-6229",
        "name":           "Lena Hoffmann",
        "plan":           "business",
        "is_vip":         True,
        "account_health": "healthy",
        "mrr":            299.00,
        "csat_average":   4.9,
        "total_tickets":  12,
        "open_tickets":   0,
        "last_contact":   "2026-01-20",
        "account_created": "2022-11-05",
        "recent_tickets": [],
        "created_at": "2022-11-05T00:00:00",
        "updated_at": "2026-01-20T00:00:00",
    },
    "C-8901": {
        "customer_ref":   "C-8901",
        "name":           "Angela Torres",
        "plan":           "enterprise",
        "is_vip":         True,
        "account_health": "healthy",
        "mrr":            999.00,
        "csat_average":   4.8,
        "total_tickets":  2,
        "open_tickets":   0,
        "last_contact":   "2026-01-15",
        "account_created": "2023-01-15",
        "recent_tickets": [],
        "created_at": "2023-01-15T00:00:00",
        "updated_at": "2026-01-15T00:00:00",
    },
}

# Identifier index: (type, value) → customer_ref
_IDENTIFIER_INDEX: dict[tuple, str] = {
    ("email", "marcus.chen@acme.io"):                    "C-1042",
    ("email", "priya.nair@startup.io"):                  "C-2817",
    ("email", "j.whitfield@techbridge.com"):             "C-3301",
    ("email", "s.reyes@marketingco.com"):                "C-4451",
    ("email", "l.hoffmann@enterprise-solutions.de"):     "C-6229",
    ("email", "a.torres@globalcorp.com"):                "C-8901",
    ("whatsapp", "+14155551042"):                        "C-1042",
    ("whatsapp", "+14155552817"):                        "C-2817",
}

# Counter for new customer refs
_NEXT_CUSTOMER_NUM = 9000


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def identify_customer(
    customer_ref: Optional[str] = None,
    email: Optional[str] = None,
    phone: Optional[str] = None,
    whatsapp_number: Optional[str] = None,
    name: Optional[str] = None,
) -> dict:
    """
    Identify a customer using multiple lookup strategies.

    Lookup order:
      1. Direct customer_ref match (fastest)
      2. Email address match
      3. Phone number match
      4. WhatsApp number match
      5. Not found → return a guest profile (not stored)

    Args:
        customer_ref:     Direct C-XXXX reference if known.
        email:            Customer's email address.
        phone:            Customer's phone number (E.164 format preferred).
        whatsapp_number:  WhatsApp phone number.
        name:             Optional name hint when no other identifier works.

    Returns:
        dict with:
          - found:           bool — True if customer exists in CRM
          - customer:        dict — full customer record (or guest profile)
          - match_method:    str — "customer_ref" | "email" | "phone" | "whatsapp" | "guest"
    """
    # Strategy 1: Direct ref
    if customer_ref and customer_ref in _CUSTOMER_STORE:
        return {
            "found": True,
            "customer": _CUSTOMER_STORE[customer_ref],
            "match_method": "customer_ref",
        }

    # Strategy 2: Email
    if email:
        ref = _IDENTIFIER_INDEX.get(("email", email.lower().strip()))
        if ref:
            return {
                "found": True,
                "customer": _CUSTOMER_STORE[ref],
                "match_method": "email",
            }

    # Strategy 3: Phone
    if phone:
        ref = _IDENTIFIER_INDEX.get(("phone", phone.strip()))
        if ref:
            return {
                "found": True,
                "customer": _CUSTOMER_STORE[ref],
                "match_method": "phone",
            }

    # Strategy 4: WhatsApp
    if whatsapp_number:
        ref = _IDENTIFIER_INDEX.get(("whatsapp", whatsapp_number.strip()))
        if ref:
            return {
                "found": True,
                "customer": _CUSTOMER_STORE[ref],
                "match_method": "whatsapp",
            }

    # Strategy 5: Not found — return guest profile
    guest_name = name or "Valued Customer"
    return {
        "found": False,
        "customer": _make_guest_profile(guest_name, email, phone, whatsapp_number),
        "match_method": "guest",
    }


def create_customer(
    name: str,
    plan: str = "starter",
    email: Optional[str] = None,
    phone: Optional[str] = None,
    whatsapp_number: Optional[str] = None,
    is_vip: bool = False,
    mrr: Optional[float] = None,
) -> dict:
    """
    Register a new customer in the CRM.

    Generates a unique customer_ref and indexes all provided identifiers.

    Args:
        name:             Full name of the customer.
        plan:             Subscription plan: starter | growth | business | enterprise.
        email:            Primary email address.
        phone:            Phone number.
        whatsapp_number:  WhatsApp number.
        is_vip:           VIP flag.
        mrr:              Monthly recurring revenue.

    Returns:
        The newly created customer dict.
    """
    global _NEXT_CUSTOMER_NUM
    _NEXT_CUSTOMER_NUM += 1
    now = datetime.utcnow().isoformat()

    customer_ref = f"C-{_NEXT_CUSTOMER_NUM}"
    customer = {
        "customer_ref":   customer_ref,
        "name":           name,
        "plan":           plan,
        "is_vip":         is_vip,
        "account_health": "healthy",
        "mrr":            mrr,
        "csat_average":   None,
        "total_tickets":  0,
        "open_tickets":   0,
        "last_contact":   None,
        "account_created": now,
        "recent_tickets": [],
        "created_at":     now,
        "updated_at":     now,
    }

    _CUSTOMER_STORE[customer_ref] = customer

    # Index identifiers
    if email:
        _IDENTIFIER_INDEX[("email", email.lower().strip())] = customer_ref
    if phone:
        _IDENTIFIER_INDEX[("phone", phone.strip())] = customer_ref
    if whatsapp_number:
        _IDENTIFIER_INDEX[("whatsapp", whatsapp_number.strip())] = customer_ref

    return customer


def get_customer_history(customer_ref: str, ticket_limit: int = 10) -> dict:
    """
    Retrieve a customer's full profile and recent ticket history.

    Args:
        customer_ref:   The customer reference (e.g., "C-1042").
        ticket_limit:   Maximum number of recent tickets to return.

    Returns:
        dict with customer profile and paginated recent_tickets.
    """
    customer = _CUSTOMER_STORE.get(customer_ref)
    if not customer:
        return {
            "found":          False,
            "customer_ref":   customer_ref,
            "customer":       None,
            "recent_tickets": [],
            "retrieved_at":   datetime.utcnow().isoformat(),
        }

    recent = customer.get("recent_tickets", [])[:ticket_limit]
    return {
        "found":          True,
        "customer_ref":   customer_ref,
        "customer":       customer,
        "recent_tickets": recent,
        "retrieved_at":   datetime.utcnow().isoformat(),
    }


def update_customer_stats(
    customer_ref: str,
    open_delta: int = 0,
    total_delta: int = 0,
    csat_score: Optional[float] = None,
) -> Optional[dict]:
    """
    Update customer ticket counters and CSAT after ticket events.

    Args:
        customer_ref:  Customer reference.
        open_delta:    +1 when ticket opened, -1 when resolved/escalated.
        total_delta:   +1 when a ticket is created.
        csat_score:    New CSAT rating to fold into the rolling average.

    Returns:
        Updated customer dict, or None if customer not found.
    """
    customer = _CUSTOMER_STORE.get(customer_ref)
    if not customer:
        return None

    customer["open_tickets"]  = max(0, customer["open_tickets"]  + open_delta)
    customer["total_tickets"] = max(0, customer["total_tickets"] + total_delta)
    customer["last_contact"]  = datetime.utcnow().isoformat()
    customer["updated_at"]    = datetime.utcnow().isoformat()

    if csat_score is not None:
        current_avg   = customer.get("csat_average")
        current_total = customer["total_tickets"]
        if current_avg is None:
            customer["csat_average"] = csat_score
        else:
            # Rolling average approximation
            customer["csat_average"] = round(
                (current_avg * (current_total - 1) + csat_score) / current_total, 2
            )

    return customer


# ---------------------------------------------------------------------------
# Internal Helpers
# ---------------------------------------------------------------------------

def _make_guest_profile(
    name: str,
    email: Optional[str],
    phone: Optional[str],
    whatsapp_number: Optional[str],
) -> dict:
    """Return a transient guest profile for unrecognized contacts."""
    return {
        "customer_ref":    "GUEST",
        "name":            name,
        "plan":            "starter",
        "is_vip":          False,
        "account_health":  "unknown",
        "mrr":             None,
        "csat_average":    None,
        "total_tickets":   0,
        "open_tickets":    0,
        "last_contact":    None,
        "account_created": None,
        "recent_tickets":  [],
        "contact_email":   email,
        "contact_phone":   phone,
        "contact_whatsapp": whatsapp_number,
        "is_guest":        True,
    }
