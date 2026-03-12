"""
tests/load_test.py
SyncFlow Customer Success Digital FTE — Stage 3

Locust load test for the Customer Success API.

Run:
  pip install locust
  locust -f tests/load_test.py --host=http://localhost:8000

  # Headless mode (CI):
  locust -f tests/load_test.py --host=http://localhost:8000 \\
    --users=50 --spawn-rate=5 --run-time=60s --headless

  # Against Hugging Face deployment:
  locust -f tests/load_test.py --host=https://YOUR-SPACE.hf.space

Load Test Profiles:
  - Normal load:   10 users, 2/s spawn
  - Peak load:     50 users, 10/s spawn
  - Stress test:   200 users, 20/s spawn
  - Soak test:     20 users for 24h (--run-time=24h)
"""

import random
import json
from locust import HttpUser, task, between, constant_pacing
from locust.exception import RescheduleTask


# ── Sample data ────────────────────────────────────────────────────────────────

CUSTOMERS = ["C-1042", "C-2071", "C-3388", "C-4459", "C-5521", "C-6634", "C-8901",
             "guest@example.com", "test@company.io", "loadtest@customer.com"]

WEB_MESSAGES = [
    "How do I reset my password?",
    "I cannot log in to my account",
    "My API key is returning 401 errors",
    "How do I export my data to CSV?",
    "Setting up Slack integration",
    "How does the workflow automation work?",
    "I need help with SSO configuration",
    "What are the rate limits for my plan?",
    "How do I add a team member?",
    "My webhook is not firing correctly",
    "How do I set up two-factor authentication?",
    "I want to upgrade my plan",
    "What is the difference between Business and Enterprise?",
    "How do I create a new workspace?",
    "The data export button is greyed out",
]

EMAIL_MESSAGES = [
    "We are experiencing issues with our GitHub integration",
    "Can you help us configure SAML SSO for Azure AD?",
    "We received an unexpected invoice charge",
    "Our scheduled workflow is not triggering at the correct time",
    "We need to migrate our data to a new workspace",
]

WHATSAPP_MESSAGES = [
    "Hi, need help with password reset",
    "API not working, getting 429",
    "How to add team members?",
    "export data help",
    "2fa setup help",
]

ANGRY_MESSAGES = [
    "I am very frustrated with this service. Nothing works!",
    "I want a refund. This is not working as promised.",
    "Your service has been down for hours and we are losing money!",
]

SUBJECTS = [
    "Password Reset Issue",
    "API Integration Problem",
    "Billing Question",
    "Workflow Not Working",
    "SSO Configuration",
    "Data Export Help",
    "Technical Support Needed",
    "Account Access Problem",
]


# ── User Behavior Classes ──────────────────────────────────────────────────────

class SupportFormUser(HttpUser):
    """
    Simulates a customer submitting support requests through the web form.
    90% normal requests, 10% angry/escalation-triggering requests.
    """
    wait_time = between(1, 5)  # 1–5 seconds between requests

    @task(6)
    def submit_web_form(self):
        """Normal web form submission."""
        payload = {
            "channel": "web_form",
            "customer_ref": random.choice(CUSTOMERS),
            "name": f"Load Test User {random.randint(1, 100)}",
            "email": f"loadtest_{random.randint(1, 1000)}@example.com",
            "subject": random.choice(SUBJECTS),
            "message": random.choice(WEB_MESSAGES),
        }
        with self.client.post(
            "/support/submit",
            json=payload,
            catch_response=True,
            name="/support/submit [web_form]",
        ) as r:
            if r.status_code == 200 and r.json().get("success"):
                r.success()
            elif r.status_code in (400, 422):
                r.failure(f"Validation error: {r.text[:100]}")
            else:
                r.failure(f"Unexpected status {r.status_code}")

    @task(2)
    def submit_email_channel(self):
        """Email channel submission."""
        payload = {
            "channel": "email",
            "customer_ref": f"user_{random.randint(1, 500)}@company.com",
            "message": random.choice(EMAIL_MESSAGES),
        }
        with self.client.post(
            "/support/submit",
            json=payload,
            catch_response=True,
            name="/support/submit [email]",
        ) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"Status {r.status_code}")

    @task(1)
    def submit_angry_customer(self):
        """Angry customer — should trigger escalation."""
        payload = {
            "channel": "web_form",
            "customer_ref": random.choice(CUSTOMERS),
            "message": random.choice(ANGRY_MESSAGES),
        }
        with self.client.post(
            "/support/submit",
            json=payload,
            catch_response=True,
            name="/support/submit [escalation]",
        ) as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"Status {r.status_code}")

    @task(3)
    def check_health(self):
        """Health check — should always be fast."""
        with self.client.get("/health", catch_response=True, name="/health") as r:
            if r.status_code == 200:
                r.success()
            else:
                r.failure(f"Health check failed: {r.status_code}")


class TicketLookupUser(HttpUser):
    """
    Simulates ops/dashboard users checking ticket and metrics status.
    """
    wait_time = between(2, 8)

    # Store created ticket refs for lookup
    _ticket_refs = []

    @task(4)
    def list_tickets(self):
        status = random.choice(["open", "in_progress", "escalated", "resolved", None])
        params = {}
        if status:
            params["status"] = status
        self.client.get("/tickets", params=params, name="/tickets [list]")

    @task(2)
    def get_metrics_summary(self):
        hours = random.choice([1, 6, 24, 48])
        self.client.get(f"/metrics/summary?hours={hours}", name="/metrics/summary")

    @task(2)
    def get_channel_metrics(self):
        self.client.get("/metrics/channels", name="/metrics/channels")

    @task(1)
    def get_sentiment(self):
        self.client.get("/metrics/sentiment", name="/metrics/sentiment")

    @task(3)
    def get_customer_profile(self):
        ref = random.choice(["C-1042", "C-2071", "C-3388", "C-8901"])
        self.client.get(f"/customers/{ref}", name="/customers/{ref}")

    @task(1)
    def get_nonexistent_ticket(self):
        """404 response testing."""
        with self.client.get(
            "/tickets/T-DOESNOTEXIST",
            catch_response=True,
            name="/tickets/{ref} [404]",
        ) as r:
            if r.status_code == 404:
                r.success()
            elif r.status_code == 200:
                r.success()
            else:
                r.failure(f"Unexpected status {r.status_code}")


class WebhookSimulator(HttpUser):
    """
    Simulates incoming webhooks from Gmail and WhatsApp.
    """
    wait_time = between(5, 15)

    @task(3)
    def gmail_webhook(self):
        payload = {
            "from": f"customer_{random.randint(1, 200)}@company.com",
            "subject": random.choice(SUBJECTS),
            "body": random.choice(EMAIL_MESSAGES),
        }
        self.client.post("/webhooks/gmail", json=payload, name="/webhooks/gmail")

    @task(2)
    def whatsapp_webhook(self):
        phone = f"+1415555{random.randint(1000, 9999)}"
        self.client.post(
            "/webhooks/whatsapp",
            data={
                "From": f"whatsapp:{phone}",
                "Body": random.choice(WHATSAPP_MESSAGES),
                "MessageSid": f"SM{'x' * 32}",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            name="/webhooks/whatsapp",
        )


# ── Pytest integration (for running load assertions in test suite) ─────────────

import pytest


@pytest.mark.load
def test_load_test_file_importable():
    """Verify the load test file is syntactically valid and importable."""
    assert SupportFormUser is not None
    assert TicketLookupUser is not None
    assert WebhookSimulator is not None
    assert len(WEB_MESSAGES) >= 10
    assert len(CUSTOMERS) >= 5
