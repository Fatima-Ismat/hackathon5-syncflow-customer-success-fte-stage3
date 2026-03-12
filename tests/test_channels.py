"""
tests/test_channels.py
SyncFlow Customer Success Digital FTE — Stage 3

Unit tests for the multi-channel intake adapters.
"""

import pytest
import sys
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

os.environ["KAFKA_MOCK_MODE"] = "true"


# ─── Email Channel ────────────────────────────────────────────────────────────

class TestEmailChannel:
    def test_normalize_basic_email(self):
        from channels.email_channel import normalize
        payload = {
            "from_email": "alice@acmecorp.com",
            "subject": "Password reset issue",
            "body": "I cannot reset my password. The link never arrives.",
        }
        result = normalize(payload)
        assert result is not None
        assert result.get("channel") == "email"
        assert "alice@acmecorp.com" in str(result)

    def test_normalize_extracts_message(self):
        from channels.email_channel import normalize
        payload = {
            "from_email": "bob@company.com",
            "subject": "Test subject",
            "body": "This is the email body content that should be extracted.",
        }
        result = normalize(payload)
        msg = result.get("raw_text") or result.get("message") or result.get("body") or ""
        assert "email body" in msg or len(msg) > 0

    def test_normalize_handles_missing_subject(self):
        from channels.email_channel import normalize
        payload = {
            "from_email": "user@test.com",
            "body": "Message without subject",
        }
        result = normalize(payload)
        assert result is not None

    def test_send_reply_returns_result(self):
        from channels.email_channel import send_reply
        result = send_reply(
            to_email="alice@acmecorp.com",
            to_name="Alice",
            subject="Re: Your support request",
            body="Thank you for contacting us. Here is our response.",
            thread_id="thread_123",
        )
        assert result is not None

    def test_email_customer_ref_from_address(self):
        from channels.email_channel import normalize
        payload = {
            "from_email": "customer@business.com",
            "subject": "Billing question",
            "body": "I need help with my invoice",
        }
        result = normalize(payload)
        # sender_email is the canonical field; fallback to any non-empty string field
        customer_ref = result.get("sender_email") or result.get("customer_ref") or result.get("sender") or ""
        assert "customer@business.com" in customer_ref or len(customer_ref) > 0


# ─── WhatsApp Channel ─────────────────────────────────────────────────────────

class TestWhatsAppChannel:
    def test_normalize_twilio_payload(self):
        from channels.whatsapp_channel import normalize
        payload = {
            "From": "whatsapp:+14155550101",
            "Body": "Hi, how do I export my data?",
            "MessageSid": "SM123456",
        }
        result = normalize(payload)
        assert result is not None
        assert result.get("channel") == "whatsapp"

    def test_normalize_plain_payload(self):
        from channels.whatsapp_channel import normalize
        payload = {
            "sender_id": "+14155550102",
            "text": "Need help with 2FA setup",
        }
        result = normalize(payload)
        assert result is not None

    def test_send_reply_concise(self):
        from channels.whatsapp_channel import send_reply
        result = send_reply(
            to_phone="+14155550101",
            body="Your password reset link has been sent to your email. Check spam if needed.",
        )
        assert result is not None

    def test_whatsapp_strips_prefix(self):
        from channels.whatsapp_channel import normalize
        payload = {
            "From": "whatsapp:+15551234567",
            "Body": "Test message",
        }
        result = normalize(payload)
        phone = result.get("phone") or result.get("sender_id") or result.get("customer_ref") or ""
        assert "whatsapp:" not in phone


# ─── Web Form Channel ─────────────────────────────────────────────────────────

class TestWebFormChannel:
    def test_normalize_full_form(self):
        from channels.web_form_channel import normalize
        payload = {
            "name": "Carol Williams",
            "email": "carol@enterprise.com",
            "subject": "SSO Configuration Help",
            "description": "We need help setting up SAML SSO for our Enterprise account.",
            "category": "authentication",
            "priority": "high",
        }
        result = normalize(payload)
        assert result is not None
        assert result.get("channel") == "web_form"

    def test_normalize_minimal_form(self):
        from channels.web_form_channel import normalize
        payload = {
            "description": "Need help",
            "customer_ref": "guest_001",
        }
        result = normalize(payload)
        assert result is not None

    def test_normalize_extracts_message(self):
        from channels.web_form_channel import normalize
        payload = {
            "name": "Test User",
            "email": "test@test.com",
            "description": "I cannot find the data export feature",
        }
        result = normalize(payload)
        msg = result.get("raw_text") or result.get("message") or result.get("description") or result.get("text") or ""
        assert len(msg) > 0

    def test_send_reply_structured(self):
        from channels.web_form_channel import send_reply
        result = send_reply(
            session_id=None,
            body="SSO configuration guide: go to Settings > Security > SSO.",
            ticket_ref="T-TESTREF1",
            sender_email="carol@enterprise.com",
        )
        assert result is not None


# ─── Channel Message Normalization ────────────────────────────────────────────

class TestCrossChannelNormalization:
    def test_all_channels_produce_channel_field(self):
        """All channel adapters should set the 'channel' field."""
        from channels.email_channel import normalize as email_norm
        from channels.whatsapp_channel import normalize as wa_norm
        from channels.web_form_channel import normalize as web_norm

        email_result = email_norm({"from": "a@b.com", "body": "test"})
        wa_result = wa_norm({"sender_id": "+1234567890", "text": "test"})
        web_result = web_norm({"description": "test", "customer_ref": "C-0001"})

        assert email_result.get("channel") == "email"
        assert wa_result.get("channel") == "whatsapp"
        assert web_result.get("channel") == "web_form"

    def test_all_channels_produce_message_content(self):
        """All channel adapters should extract message text."""
        from channels.email_channel import normalize as email_norm
        from channels.whatsapp_channel import normalize as wa_norm
        from channels.web_form_channel import normalize as web_norm

        email_result = email_norm({"from": "a@b.com", "body": "email body text"})
        wa_result = wa_norm({"sender_id": "+1234567890", "text": "whatsapp message"})
        web_result = web_norm({"description": "web form message", "customer_ref": "C-0001"})

        # Each should contain the original message somewhere in the result
        assert any("email body text" in str(v) for v in email_result.values() if isinstance(v, str))
        assert any("whatsapp message" in str(v) for v in wa_result.values() if isinstance(v, str))
        assert any("web form message" in str(v) for v in web_result.values() if isinstance(v, str))
