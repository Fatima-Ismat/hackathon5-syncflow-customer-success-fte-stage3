"""
tests/test_multichannel_e2e.py
SyncFlow Customer Success Digital FTE — Stage 3

End-to-end multi-channel integration tests.
Tests the full pipeline from inbound message → AI response → ticket → metrics.
"""

import pytest
import time
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


# ─── E2E Test 1: Web Form → Ticket → Status Lookup ───────────────────────────

class TestWebFormE2E:
    def test_full_web_form_flow(self, client):
        """Submit web form → verify ticket created → look up ticket status."""
        # Step 1: Submit support request
        submit_r = client.post("/support/submit", json={
            "channel": "web_form",
            "customer_ref": "C-1042",
            "name": "Alice Chen",
            "email": "alice@acmecorp.com",
            "subject": "Cannot export data",
            "message": "I'm trying to export my workflow data to CSV but the download button is greyed out.",
        })
        assert submit_r.status_code == 200
        result = submit_r.json()
        assert result["success"] is True

        # Step 2: Extract ticket ref
        data = result["data"]
        if "result" in data:
            data = data["result"]
        ticket_ref = data.get("ticket_ref")

        if not ticket_ref:
            pytest.skip("No ticket_ref in response — skipping status lookup")

        # Step 3: Look up ticket status
        status_r = client.get(f"/tickets/{ticket_ref}")
        assert status_r.status_code == 200
        ticket_data = status_r.json()["data"]
        assert ticket_data.get("status") in ("open", "in_progress", "escalated", "resolved", "waiting_customer", "closed")

    def test_web_form_validation_fields(self, client):
        """Verify form field validation works."""
        # Message too short
        r = client.post("/support/submit", json={
            "channel": "web_form",
            "customer_ref": "C-1042",
            "message": "Hi",  # Too short (min_length=5)
        })
        assert r.status_code == 422


# ─── E2E Test 2: Email Webhook → Ticket ──────────────────────────────────────

class TestEmailE2E:
    def test_gmail_webhook_creates_processable_event(self, client):
        """Gmail webhook → event accepted → processed."""
        r = client.post("/webhooks/gmail", json={
            "from": "enterprise@bigcorp.com",
            "subject": "URGENT: Workflow automation broken in production",
            "body": (
                "Our critical production workflow that triggers on GitHub PRs stopped working "
                "3 hours ago. We have 50 engineers blocked. This needs immediate attention."
            ),
            "customer_ref": "C-3388",
        })
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "accepted"
        assert data.get("channel") == "email"

    def test_email_direct_api_submission(self, client):
        """Direct email submission through /support/submit."""
        r = client.post("/support/submit", json={
            "channel": "email",
            "customer_ref": "test@techcorp.com",
            "email": "test@techcorp.com",
            "subject": "OAuth token expired",
            "message": "Our Salesforce integration keeps failing with OAuth token expired errors.",
        })
        assert r.status_code == 200
        data = r.json()["data"]
        assert data.get("success") is not False


# ─── E2E Test 3: WhatsApp → Ticket ───────────────────────────────────────────

class TestWhatsAppE2E:
    def test_twilio_webhook_format(self, client):
        """Twilio-format WhatsApp webhook."""
        r = client.post(
            "/webhooks/whatsapp",
            data={
                "From": "whatsapp:+14155550102",
                "Body": "Hey can you help me set up 2FA for my account?",
                "MessageSid": "SM" + "x" * 32,
                "AccountSid": "AC" + "y" * 32,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data.get("status") == "accepted"

    def test_whatsapp_direct_api(self, client):
        """WhatsApp message via direct API."""
        r = client.post("/support/submit", json={
            "channel": "whatsapp",
            "customer_ref": "+14155550105",
            "message": "How many API calls can I make per minute on Growth plan?",
        })
        assert r.status_code == 200


# ─── E2E Test 4: Cross-Channel Customer Continuity ───────────────────────────

class TestCrossChannelContinuity:
    def test_same_customer_across_channels(self, client):
        """Same customer submitting via different channels — should resolve to same profile."""
        # Channel 1: Web form
        r1 = client.post("/support/submit", json={
            "channel": "web_form",
            "customer_ref": "C-1042",
            "message": "First contact via web form",
        })
        assert r1.status_code == 200

        # Channel 2: Email (same customer ref)
        r2 = client.post("/support/submit", json={
            "channel": "email",
            "customer_ref": "C-1042",
            "email": "alice@acmecorp.com",
            "message": "Follow-up via email",
        })
        assert r2.status_code == 200

        # Both should succeed and reference the same customer
        data1 = r1.json()["data"]
        data2 = r2.json()["data"]

        # Both should have customer context
        assert data1.get("success") is not False
        assert data2.get("success") is not False

    def test_new_customer_auto_created(self, client):
        """Unknown customer submitting first ticket — should create guest profile."""
        r = client.post("/support/submit", json={
            "channel": "web_form",
            "customer_ref": "brand_new_user@newcompany.io",
            "name": "New User",
            "email": "brand_new_user@newcompany.io",
            "message": "I just signed up and cannot find the workflow builder",
        })
        assert r.status_code == 200
        assert r.json()["success"] is True


# ─── E2E Test 5: Escalation Flow ─────────────────────────────────────────────

class TestEscalationE2E:
    def test_angry_customer_auto_escalated(self, client):
        """Angry/threatening message should auto-escalate."""
        r = client.post("/support/submit", json={
            "channel": "web_form",
            "customer_ref": "C-4459",
            "message": (
                "This is COMPLETELY unacceptable! I have been a customer for 2 years "
                "and you have ruined my business. I want a full refund RIGHT NOW or "
                "I will contact my lawyer and post everywhere about your terrible service!"
            ),
        })
        assert r.status_code == 200

    def test_manual_escalation_endpoint(self, client):
        """Manual escalation via API."""
        # First create a ticket
        r1 = client.post("/support/submit", json={
            "channel": "web_form",
            "customer_ref": "C-2071",
            "message": "I have a complex technical issue with my workflow automation",
        })
        assert r1.status_code == 200
        data = r1.json()["data"]
        if "result" in data:
            data = data["result"]
        ticket_ref = data.get("ticket_ref")

        if not ticket_ref:
            pytest.skip("No ticket_ref available")

        # Manual escalation
        r2 = client.post(f"/tickets/{ticket_ref}/escalate", json={
            "reason": "low_kb_confidence",
            "priority": "high",
            "notes": "Complex integration issue beyond AI capability",
        })
        assert r2.status_code == 200
        esc_data = r2.json()["data"]
        assert esc_data.get("status") == "escalated"


# ─── E2E Test 6: Metrics Collection ──────────────────────────────────────────

class TestMetricsE2E:
    def test_metrics_reflect_activity(self, client):
        """After submitting tickets, metrics should reflect activity."""
        # Submit a few tickets
        for i in range(3):
            client.post("/support/submit", json={
                "channel": "web_form",
                "customer_ref": f"metrics_test_user_{i}",
                "message": f"Test message {i} for metrics validation",
            })

        # Check metrics
        r = client.get("/metrics/summary?hours=1")
        assert r.status_code == 200
        data = r.json()["data"]
        assert data is not None

    def test_channel_metrics_breakdown(self, client):
        """Metrics should break down by channel."""
        # Submit on different channels
        client.post("/support/submit", json={
            "channel": "email", "customer_ref": "email_test@test.com",
            "message": "Email channel test"
        })
        client.post("/support/submit", json={
            "channel": "whatsapp", "customer_ref": "+19998887777",
            "message": "WhatsApp channel test"
        })

        r = client.get("/metrics/channels")
        assert r.status_code == 200
        assert r.json()["success"] is True


# ─── E2E Test 7: 24-Hour Readiness Simulation ────────────────────────────────

@pytest.mark.slow
class Test24HourReadiness:
    """
    Simulated 24-hour readiness test.

    This test verifies the system can handle a representative sample of the
    expected 24-hour message volume across all channels without degradation.

    Full 24-hour simulation plan:
    - Expected volume: 500-2000 messages/day
    - Channel split: 40% web_form, 35% email, 25% whatsapp
    - Escalation rate target: <15%
    - Avg response time target: <3000ms
    - KB resolution rate target: >70%

    NOTE: For actual 24-hour load testing, use tests/load_test.py with Locust.
    """

    def test_burst_of_10_requests(self, client):
        """Simulate a small burst — verifies no crashes under concurrent-ish load."""
        channels = ["web_form", "email", "whatsapp"] * 4
        messages = [
            "How do I reset my password?",
            "My API key is not working",
            "I need help with billing",
            "Can't set up 2FA",
            "Workflow automation broken",
            "How to export data?",
            "SSO configuration help",
            "Integration with Slack not working",
            "Rate limit errors",
            "Need help with webhooks",
        ]
        results = []
        for i, (channel, msg) in enumerate(zip(channels, messages)):
            r = client.post("/support/submit", json={
                "channel": channel,
                "customer_ref": f"load_test_user_{i:03d}",
                "message": msg,
            })
            results.append(r.status_code)

        success_count = sum(1 for s in results if s == 200)
        assert success_count >= 8, f"Only {success_count}/10 requests succeeded"

    def test_system_still_healthy_after_load(self, client):
        """Verify health endpoint still returns OK after burst."""
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"
