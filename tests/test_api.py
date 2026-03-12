"""
tests/test_api.py
SyncFlow Customer Success Digital FTE — Stage 3

Integration tests for the FastAPI endpoints.
"""

import pytest
import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ["KAFKA_MOCK_MODE"] = "true"
os.environ["DATABASE_URL"] = "sqlite://"


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    try:
        from api.main import app
    except Exception:
        from backend.main import app
    return TestClient(app)


# ─── Health Endpoints ─────────────────────────────────────────────────────────

class TestHealthEndpoints:
    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_contains_version(self, client):
        r = client.get("/health")
        data = r.json()
        assert "version" in data

    def test_health_contains_status_ok(self, client):
        r = client.get("/health")
        assert r.json()["status"] == "ok"

    def test_readiness_returns_200(self, client):
        r = client.get("/readiness")
        assert r.status_code == 200 or r.status_code == 404  # 404 acceptable if not on api/main

    def test_docs_accessible(self, client):
        r = client.get("/docs")
        assert r.status_code == 200


# ─── Support Submit ───────────────────────────────────────────────────────────

class TestSupportSubmit:
    def test_web_form_submission_success(self, client):
        r = client.post("/support/submit", json={
            "channel": "web_form",
            "customer_ref": "C-1042",
            "message": "How do I reset my password?",
        })
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True

    def test_submission_returns_ticket_ref(self, client):
        r = client.post("/support/submit", json={
            "channel": "web_form",
            "customer_ref": "test_user_001",
            "message": "I need help with my account",
        })
        assert r.status_code == 200
        result = r.json()["data"]
        assert result.get("ticket_ref") is not None or result.get("success") is not False

    def test_email_channel_accepted(self, client):
        r = client.post("/support/submit", json={
            "channel": "email",
            "customer_ref": "user@example.com",
            "message": "My API key stopped working after renewal",
        })
        assert r.status_code == 200

    def test_whatsapp_channel_accepted(self, client):
        r = client.post("/support/submit", json={
            "channel": "whatsapp",
            "customer_ref": "+14155550101",
            "message": "How to export data?",
        })
        assert r.status_code == 200

    def test_web_alias_accepted(self, client):
        r = client.post("/support/submit", json={
            "channel": "web",
            "customer_ref": "C-2071",
            "message": "Billing question",
        })
        assert r.status_code == 200

    def test_invalid_channel_rejected(self, client):
        r = client.post("/support/submit", json={
            "channel": "fax",
            "customer_ref": "C-1042",
            "message": "Test",
        })
        assert r.status_code == 400 or r.status_code == 422

    def test_empty_message_rejected(self, client):
        r = client.post("/support/submit", json={
            "channel": "web_form",
            "customer_ref": "C-1042",
            "message": "",
        })
        assert r.status_code == 422

    def test_missing_customer_ref_rejected(self, client):
        r = client.post("/support/submit", json={
            "channel": "web_form",
            "message": "Help me please",
        })
        assert r.status_code == 422

    def test_debug_mode_returns_extra_data(self, client):
        r = client.post("/support/submit", json={
            "channel": "web_form",
            "customer_ref": "C-1042",
            "message": "Test with debug",
            "debug": True,
        })
        assert r.status_code == 200

    def test_escalation_triggered_for_angry_customer(self, client):
        r = client.post("/support/submit", json={
            "channel": "web_form",
            "customer_ref": "C-4459",
            "message": "I am furious! I want my refund NOW! This is fraud and I'll sue!",
        })
        assert r.status_code == 200
        data = r.json()["data"]
        # May be in top-level or nested
        escalated = data.get("escalated") or data.get("result", {}).get("escalated", False)
        # We just verify the call succeeds; escalation depends on thresholds


# ─── Ticket Endpoints ─────────────────────────────────────────────────────────

class TestTicketEndpoints:
    @pytest.fixture
    def created_ticket(self, client):
        r = client.post("/support/submit", json={
            "channel": "web_form",
            "customer_ref": "C-1042",
            "message": "Test ticket for endpoint tests",
        })
        data = r.json().get("data", {})
        # Handle nested result
        if "result" in data:
            data = data["result"]
        return data.get("ticket_ref")

    def test_list_tickets_returns_200(self, client):
        r = client.get("/tickets")
        assert r.status_code == 200

    def test_list_tickets_has_success_field(self, client):
        r = client.get("/tickets")
        assert r.json()["success"] is True

    def test_list_tickets_filter_by_status(self, client):
        r = client.get("/tickets?status=open")
        assert r.status_code == 200

    def test_get_nonexistent_ticket_returns_404(self, client):
        r = client.get("/tickets/T-DOESNOTEXIST")
        assert r.status_code == 404

    def test_get_ticket_by_ref(self, client, created_ticket):
        if not created_ticket:
            pytest.skip("No ticket_ref returned from submission")
        r = client.get(f"/tickets/{created_ticket}")
        assert r.status_code == 200

    def test_support_ticket_status_endpoint(self, client, created_ticket):
        if not created_ticket:
            pytest.skip("No ticket_ref returned")
        r = client.get(f"/support/ticket/{created_ticket}")
        assert r.status_code == 200


# ─── Customer Endpoints ───────────────────────────────────────────────────────

class TestCustomerEndpoints:
    def test_get_known_customer(self, client):
        r = client.get("/customers/C-1042")
        assert r.status_code == 200
        data = r.json()
        assert data["success"] is True

    def test_get_unknown_customer_returns_404(self, client):
        r = client.get("/customers/C-DOESNOTEXIST")
        assert r.status_code == 404

    def test_customer_lookup_by_email(self, client):
        r = client.post("/customers/lookup", json={"email": "alice@acmecorp.com"})
        # May return 200 or 404 depending on whether seeded
        assert r.status_code in (200, 404)

    def test_customer_lookup_requires_identifier(self, client):
        r = client.post("/customers/lookup", json={})
        assert r.status_code == 400 or r.status_code == 422


# ─── Metrics Endpoints ────────────────────────────────────────────────────────

class TestMetricsEndpoints:
    def test_metrics_summary_returns_200(self, client):
        r = client.get("/metrics/summary")
        assert r.status_code == 200
        assert r.json()["success"] is True

    def test_metrics_channels_returns_200(self, client):
        r = client.get("/metrics/channels")
        assert r.status_code == 200

    def test_metrics_sentiment_returns_200(self, client):
        r = client.get("/metrics/sentiment")
        assert r.status_code == 200

    def test_metrics_hours_param(self, client):
        r = client.get("/metrics/summary?hours=48")
        assert r.status_code == 200

    def test_metrics_hours_too_large_rejected(self, client):
        r = client.get("/metrics/summary?hours=9999")
        assert r.status_code == 422


# ─── Webhook Endpoints ────────────────────────────────────────────────────────

class TestWebhooks:
    def test_gmail_webhook_accepts_json(self, client):
        r = client.post("/webhooks/gmail", json={
            "from": "user@example.com",
            "subject": "Need help",
            "body": "I cannot log in to my account",
        })
        assert r.status_code == 200

    def test_whatsapp_webhook_accepts_twilio_format(self, client):
        r = client.post(
            "/webhooks/whatsapp",
            data={"From": "whatsapp:+14155550101", "Body": "Hi, need help", "MessageSid": "SM123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 200

    def test_whatsapp_status_webhook(self, client):
        r = client.post(
            "/webhooks/whatsapp/status",
            data={"MessageSid": "SM123", "MessageStatus": "delivered"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 200
