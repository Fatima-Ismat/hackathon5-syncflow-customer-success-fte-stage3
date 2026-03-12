"""
tests/conftest.py
SyncFlow Customer Success Digital FTE — Stage 3

Shared pytest fixtures for all test modules.
"""

import sys
import os
import asyncio
import pytest

# Add repo root to path
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# Force mock mode for all tests
os.environ["KAFKA_MOCK_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite://"  # in-memory SQLite
os.environ.setdefault("OPENAI_API_KEY", "sk-test-mock-key-for-testing-only")


# ─── Windows: prevent ThreadPoolExecutor shutdown delay ──────────────────────
# On Windows, the default ProactorEventLoop can hang for 1-3s on process exit
# while cleaning up executor threads.  Switching to SelectorEventLoop avoids it.
def pytest_configure(config):
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture(scope="session")
def api_client():
    """TestClient for the FastAPI app."""
    from fastapi.testclient import TestClient
    # Try new api/main.py first, fall back to backend/main.py
    try:
        from api.main import app
    except ImportError:
        from backend.main import app
    return TestClient(app)


@pytest.fixture(scope="session")
def backend_client():
    """TestClient for the legacy backend (Stage 2 compatibility)."""
    from fastapi.testclient import TestClient
    from backend.main import app
    return TestClient(app)


@pytest.fixture
def web_form_payload():
    return {
        "channel": "web_form",
        "customer_ref": "C-1042",
        "name": "Alice Chen",
        "email": "alice@acmecorp.com",
        "subject": "Password reset not working",
        "message": "I cannot reset my password. The link expires before I can use it.",
    }


@pytest.fixture
def email_payload():
    return {
        "channel": "email",
        "customer_ref": "test@example.com",
        "name": "Test User",
        "email": "test@example.com",
        "subject": "API returning 429 errors",
        "message": "I keep getting 429 rate limit errors from your API even though I'm on the Business plan.",
    }


@pytest.fixture
def whatsapp_payload():
    return {
        "channel": "whatsapp",
        "customer_ref": "+14155550101",
        "message": "Hey, how do I export my data?",
    }


@pytest.fixture
def angry_customer_payload():
    return {
        "channel": "web_form",
        "customer_ref": "C-4459",
        "message": (
            "This is absolutely ridiculous! I've been waiting 3 days for a response "
            "and no one has helped me. I want a refund immediately or I'm contacting "
            "my lawyer. This service is terrible!"
        ),
    }


@pytest.fixture
def vip_escalation_payload():
    return {
        "channel": "email",
        "customer_ref": "C-8901",
        "name": "Grace Liu",
        "email": "grace@techcorpglobal.com",
        "subject": "Critical security incident",
        "message": "We believe our account has been compromised. There are unauthorized logins.",
    }
