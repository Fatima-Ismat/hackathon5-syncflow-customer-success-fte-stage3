# API Integration Tests – Stage 2
## NovaSync Technologies / SyncFlow Customer Success Digital FTE

> **Test Environment**: `http://localhost:8000` (FastAPI dev server)
> **Run server**: `uvicorn backend.main:app --reload --port 8000`
> **Auth**: None (add Bearer token auth in Stage 3)

---

## Test Suite Overview

| Category | Tests | Coverage |
|---|---|---|
| Ticket Creation | 5 | Create, validate, SLA assignment |
| Message Routing | 4 | Channel normalization, agent dispatch |
| Escalation Triggers | 6 | All 3 tiers, queue routing |
| Conversation Continuity | 3 | Multi-turn, history passing |
| Multi-Channel | 4 | Email, WhatsApp, Web Form |
| Customer Identification | 3 | Email lookup, phone, guest |
| Metrics | 3 | Volume, channel, sentiment |
| Error Handling | 4 | Invalid input, 404, 422 |
| System | 2 | Health check, docs |

**Total: 34 test scenarios**

---

## Test 1: Health Check

```http
GET /health
```

**Expected response (200 OK):**
```json
{
  "status": "ok",
  "service": "syncflow-customer-success-api",
  "version": "2.0.0"
}
```

**Pass criteria:**
- Returns 200
- `status` is `"ok"`
- `version` is `"2.0.0"`

---

## Test 2: Email Message — Password Reset (Known Customer)

```http
POST /support/submit
Content-Type: application/json

{
  "channel": "email",
  "customer_ref": "C-1042",
  "payload": {
    "from_email": "marcus.chen@acme.io",
    "from_name": "Marcus Chen",
    "subject": "Cannot log in — forgot password",
    "body": "Hello Support,\n\nI've forgotten my password and can't log in to SyncFlow. Could you help me reset it?\n\nBest,\nMarcus"
  }
}
```

**Expected response (200 OK):**
```json
{
  "success": true,
  "data": {
    "ticket_ref": "TKT-...",
    "channel": "email",
    "customer_ref": "C-1042",
    "should_escalate": false,
    "priority": "low",
    "sentiment": "neutral",
    "kb_used": true,
    "kb_section": "Password & Security -> Password Reset",
    "agent_confidence": "> 0.40"
  }
}
```

**Pass criteria:**
- Returns 200
- `should_escalate` is `false`
- `kb_used` is `true`
- `agent_confidence` >= 0.40
- `response` contains "reset" or "app.syncflow.io"
- `ticket_ref` follows pattern `TKT-YYYYMMDD-XXXX`

---

## Test 3: WhatsApp Message — Angry Customer (Escalation)

```http
POST /support/submit
Content-Type: application/json

{
  "channel": "whatsapp",
  "payload": {
    "from_number": "+14155552817",
    "display_name": "Priya",
    "text": "THIS IS RIDICULOUS I've been waiting 3 DAYS and nobody has helped me!!! My entire business is DOWN!!!"
  }
}
```

**Expected response (200 OK):**
```json
{
  "success": true,
  "data": {
    "should_escalate": true,
    "escalation_reason": "high_anger_score",
    "priority": "high",
    "sentiment": "angry"
  }
}
```

**Pass criteria:**
- Returns 200
- `should_escalate` is `true`
- `sentiment` is `"angry"` or `"frustrated"`
- `priority` is `"high"` or `"critical"`
- `response` contains an escalation acknowledgment
- Response is < 80 words (WhatsApp channel limit)

---

## Test 4: Web Form — API Rate Limit (Auto-Resolved)

```http
POST /support/submit
Content-Type: application/json

{
  "channel": "web_form",
  "payload": {
    "email": "marcus.chen@acme.io",
    "name": "Marcus Chen",
    "issue_type": "api",
    "subject": "429 rate limit error",
    "description": "I am getting a 429 rate limit error on all API calls. My plan is Growth and I need this resolved.",
    "account_id": "C-1042"
  }
}
```

**Pass criteria:**
- Returns 200
- `should_escalate` is `false`
- `kb_section` contains "API"
- `response` contains "429" or "rate limit"
- `ticket_ref` is created with valid format

---

## Test 5: Email — Legal Threat (Tier 1 Immediate Escalation)

```http
POST /support/submit
Content-Type: application/json

{
  "channel": "email",
  "payload": {
    "from_email": "j.whitfield@techbridge.com",
    "from_name": "James Whitfield",
    "subject": "Immediate legal action required",
    "body": "Your service has cost us $50,000 in losses. We are filing a lawsuit unless this is resolved today. Our lawyers will contact you."
  }
}
```

**Pass criteria:**
- Returns 200
- `should_escalate` is `true`
- `escalation_reason` is `"legal_threat"`
- `priority` is `"critical"`
- `escalation_queue` is `"legal-team"` (visible via GET /tickets/{ref})
- Response does NOT attempt to argue, negotiate, or make promises

---

## Test 6: Ticket Creation Validation

```http
POST /support/submit
Content-Type: application/json

{
  "channel": "email",
  "payload": {
    "from_email": "new.customer@example.com",
    "from_name": "New Customer",
    "subject": "General question about billing",
    "body": "Hi, I wanted to ask about the difference between the Growth and Business plans and what the pricing is."
  }
}
```

**Pass criteria:**
- Returns 200
- `ticket_ref` is created
- Customer is identified as `GUEST` (not in CRM)
- `customer_ref` reflects guest identification
- SLA deadline is set (Growth defaults don't apply; Starter SLA used for guests)

---

## Test 7: Get Ticket by Reference

**Pre-condition**: Run Test 2 and note the `ticket_ref` from response.

```http
GET /tickets/{ticket_ref}
```

**Pass criteria:**
- Returns 200
- All fields present: `status`, `priority`, `sla_deadline`, `created_at`
- `status` is `"in_progress"` or `"waiting_customer"` (progressed from `open`)

---

## Test 8: List Tickets with Status Filter

```http
GET /tickets?status=escalated&limit=10
```

**Pass criteria:**
- Returns 200
- `data.tickets` is a list (may be empty if no escalations yet)
- All returned tickets have `status: "escalated"`
- `data.total` is a non-negative integer

---

## Test 9: Manual Ticket Escalation

**Pre-condition**: Run Test 4 and note the `ticket_ref`.

```http
POST /tickets/{ticket_ref}/escalate
Content-Type: application/json

{
  "reason": "refund_request",
  "priority": "high",
  "notes": "Customer is asking for a refund on the current billing period. Needs billing team review."
}
```

**Pass criteria:**
- Returns 200
- `data.escalation_queue` is `"billing-team"`
- `data.status` is `"escalated"`
- `data.escalation_id` follows pattern `ESC-YYYYMMDDHHMMSS-XXX`

---

## Test 10: Ticket Reply by Human Agent

**Pre-condition**: Run Test 5 (escalated ticket).

```http
POST /tickets/{ticket_ref}/reply
Content-Type: application/json

{
  "message": "Hi James, thank you for bringing this to our attention. I am personally reviewing your account and will provide a resolution within the next 30 minutes. — Sarah, Senior Support",
  "actor": "human:sarah_support",
  "send_to_customer": true
}
```

**Pass criteria:**
- Returns 200
- `data.actor` is `"human:sarah_support"`
- `data.replied_at` is a valid ISO timestamp

---

## Test 11: Get Customer Profile

```http
GET /customers/C-1042
```

**Pass criteria:**
- Returns 200
- `data.customer.name` is `"Marcus Chen"`
- `data.customer.plan` is `"growth"`
- `data.customer.account_health` is `"healthy"`
- `data.recent_tickets` is a list

---

## Test 12: Customer Not Found

```http
GET /customers/C-9999
```

**Pass criteria:**
- Returns 404
- Error message references `C-9999`

---

## Test 13: Invalid Channel

```http
POST /support/submit
Content-Type: application/json

{
  "channel": "telegram",
  "payload": {"text": "help"}
}
```

**Pass criteria:**
- Returns 400 or 422
- Error message mentions valid channels

---

## Test 14: Empty Message Body

```http
POST /support/submit
Content-Type: application/json

{
  "channel": "whatsapp",
  "payload": {
    "from_number": "+14155552817",
    "display_name": "Priya",
    "text": "   "
  }
}
```

**Pass criteria:**
- Returns 200 (not a 422 — empty messages are handled gracefully)
- `data.response` asks the customer to re-submit with details
- No ticket is created (`ticket_ref` is null)

---

## Test 15: WhatsApp — VIP Customer with Negative Sentiment (Tier 2 Escalation)

```http
POST /support/submit
Content-Type: application/json

{
  "channel": "whatsapp",
  "payload": {
    "from_number": "+14155556229",
    "display_name": "Lena",
    "text": "I have been trying to fix this integration issue for 2 days and it still does not work. This is very frustrating."
  },
  "customer_ref": "C-6229"
}
```

**Pass criteria:**
- Returns 200
- `customer_ref` is `"C-6229"` (Lena Hoffmann, VIP)
- `should_escalate` is `true`
- `escalation_reason` is `"vip_customer_negative_sentiment"` or similar
- Priority is `"high"` (VIP floor)

---

## Test 16: Multi-Turn Conversation Continuity

**Step 1** — First message:
```http
POST /support/submit
Content-Type: application/json

{
  "channel": "email",
  "customer_ref": "C-4451",
  "payload": {
    "from_email": "s.reyes@marketingco.com",
    "subject": "Workflow keeps stopping",
    "body": "My workflow stopped working again."
  }
}
```

**Step 2** — Follow-up message with conversation history:
```http
POST /support/submit
Content-Type: application/json

{
  "channel": "email",
  "customer_ref": "C-4451",
  "payload": {
    "from_email": "s.reyes@marketingco.com",
    "subject": "Re: Workflow keeps stopping",
    "body": "I tried what you suggested but it still doesn't work. This is the third time this month."
  },
  "conversation_history": [
    {"role": "customer", "content": "My workflow stopped working again.", "turn": 1},
    {"role": "agent",    "content": "Please check if the workflow status is Active...", "turn": 1}
  ]
}
```

**Pass criteria (Step 2):**
- Returns 200
- `sentiment` is `"frustrated"` (due to repeated issue + history)
- `escalation_reason` contains "frustration" or "turns" (multi-turn trigger)
- Response acknowledges the repeated issue

---

## Test 17: WhatsApp — Billing Query (Immediate Escalation)

```http
POST /support/submit
Content-Type: application/json

{
  "channel": "whatsapp",
  "payload": {
    "from_number": "+14155551042",
    "display_name": "Marcus",
    "text": "i want a refund for this month pls"
  },
  "customer_ref": "C-1042"
}
```

**Pass criteria:**
- Returns 200
- `should_escalate` is `true`
- `priority` is `"high"` (refund requests are Tier 1)
- Response word count <= 80

---

## Test 18: Concurrent Channel Messages (Multi-Channel)

Submit the same issue via different channels and verify independent ticket creation:

**Email submission:**
```http
POST /support/submit
{ "channel": "email", "payload": { "from_email": "a.torres@globalcorp.com", "subject": "SSO not working", "body": "Our Okta SSO is broken. Nobody can log in." }, "customer_ref": "C-8901" }
```

**Pass criteria:**
- Returns 200
- `kb_section` references SSO
- `priority` is `"high"` (enterprise plan + urgency)
- `customer_plan` is `"enterprise"`

---

## Test 19: Security Incident (Tier 1 Immediate Escalation)

```http
POST /support/submit
Content-Type: application/json

{
  "channel": "email",
  "payload": {
    "from_email": "s.reyes@marketingco.com",
    "from_name": "Sofia Reyes",
    "subject": "Unauthorized access to my account",
    "body": "I just received an email that someone logged into my account from Germany. I did not authorize this. I think my account has been hacked or there was a data breach."
  },
  "customer_ref": "C-4451"
}
```

**Pass criteria:**
- Returns 200
- `should_escalate` is `true`
- `escalation_reason` is `"security_incident"`
- `priority` is `"critical"`
- Response does NOT contain any account details or confirm/deny the breach

---

## Test 20: Profanity Detection (Tier 1 Escalation)

```http
POST /support/submit
Content-Type: application/json

{
  "channel": "web_form",
  "payload": {
    "email": "angry@customer.com",
    "name": "Angry Customer",
    "issue_type": "billing",
    "description": "This is absolute crap. You charged me twice and your support is complete shit."
  }
}
```

**Pass criteria:**
- Returns 200
- `should_escalate` is `true`
- Response tone is de-escalating (does NOT mirror negative language)
- Priority is `"high"` minimum

---

## Test 21: Knowledge Base — Confidence Below Threshold

```http
POST /support/submit
Content-Type: application/json

{
  "channel": "web_form",
  "payload": {
    "email": "unknown@example.com",
    "name": "Test User",
    "issue_type": "other",
    "description": "The purple giraffe feature stopped working after the last update."
  }
}
```

**Pass criteria:**
- Returns 200
- `agent_confidence` < 0.40 (unrecognized topic)
- `should_escalate` is `true` (low KB confidence trigger)
- `escalation_reason` is `"low_kb_confidence"`

---

## Test 22: Metrics Summary Endpoint

**Pre-condition**: Submit at least 3 messages via Tests 2–4.

```http
GET /metrics/summary?hours=24
```

**Pass criteria:**
- Returns 200
- `data.volume.tickets_created` >= 3
- `data.volume.responses_generated` >= 3
- `data.quality.auto_resolution_rate` is a float between 0 and 1
- `data.channel_usage` contains at least one channel key

---

## Test 23: Channel Metrics Breakdown

```http
GET /metrics/channels?hours=24
```

**Pass criteria:**
- Returns 200
- `data.channels` contains keys: `email`, `whatsapp`, `web_form`
- Each channel entry has `tickets`, `responses`, `escalations`

---

## Test 24: Sentiment Distribution

```http
GET /metrics/sentiment?hours=24
```

**Pass criteria:**
- Returns 200
- `data.distribution` contains at least one sentiment label
- All `pct` values sum to approximately 100%

---

## Test 25: Reply to Resolved Ticket (Error Case)

**Pre-condition**: Resolve a ticket manually using service layer, or run tests until a ticket auto-resolves.

```http
POST /tickets/{resolved_ticket_ref}/reply
Content-Type: application/json

{
  "message": "This ticket is already resolved.",
  "actor": "human_agent"
}
```

**Pass criteria:**
- Returns 400
- Error message mentions ticket is resolved

---

## Test 26: Escalate Resolved Ticket (Error Case)

```http
POST /tickets/{resolved_ticket_ref}/escalate
Content-Type: application/json

{
  "reason": "refund_request"
}
```

**Pass criteria:**
- Returns 400
- Error message indicates ticket is already resolved

---

## Test 27: Customer Identifier — Email Lookup

```http
POST /support/submit
Content-Type: application/json

{
  "channel": "email",
  "payload": {
    "from_email": "l.hoffmann@enterprise-solutions.de",
    "from_name": "Lena H",
    "subject": "Team seats question",
    "body": "How many seat can I add to my Business plan?"
  }
}
```

**Pass criteria:**
- Returns 200
- `customer_ref` is `"C-6229"` (identified by email, not customer_ref)
- `match_method` is `"email"` (in pipeline_stages if debug=true)
- VIP status is respected in response quality

---

## Test 28: Customer Identifier — Guest (New Contact)

```http
POST /support/submit
Content-Type: application/json

{
  "channel": "web_form",
  "payload": {
    "email": "completely.new@prospect.com",
    "name": "Brand New User",
    "issue_type": "general",
    "description": "I am evaluating SyncFlow and have a question about your API rate limits."
  }
}
```

**Pass criteria:**
- Returns 200
- `customer_ref` is `null` or `"GUEST"`
- Ticket is created with Starter plan defaults (SLA = 24 hours)
- `agent_confidence` is reasonable (API rate limit is in KB)

---

## Test 29: Ticket Status Transition — Invalid

```http
POST /support/submit
```
*(Note: Attempting to test invalid status transitions requires direct service layer access.)*

**Manual test via Python:**
```python
from crm.ticket_service import create_ticket, update_ticket_status, TicketStatus

ticket = create_ticket("C-1042", "email", "Test issue")
ref = ticket["ticket_ref"]

# Valid: OPEN → IN_PROGRESS
update_ticket_status(ref, TicketStatus.IN_PROGRESS)

# INVALID: IN_PROGRESS → OPEN (should raise ValueError)
try:
    update_ticket_status(ref, TicketStatus.OPEN)
    print("FAIL: Should have raised ValueError")
except ValueError as e:
    print(f"PASS: {e}")
```

**Pass criteria:**
- `ValueError` is raised with message describing the invalid transition

---

## Test 30: SLA Deadline Assignment by Plan

**Manual test via Python:**
```python
from crm.ticket_service import create_ticket, SLA_MATRIX

plans = ["starter", "growth", "business", "enterprise"]
priority = "high"

for plan in plans:
    ticket = create_ticket("C-1042", "email", f"Test for {plan}", priority="high", plan=plan)
    expected_hours = SLA_MATRIX[plan][priority]
    print(f"{plan}: {ticket['sla_hours']}h expected={expected_hours}h — {'PASS' if ticket['sla_hours'] == expected_hours else 'FAIL'}")
```

**Pass criteria:**
- Each plan gets the correct SLA hours from the matrix
- `sla_deadline` is `now + sla_hours` (within ~1 second tolerance)

---

## Test 31: Knowledge Service — Keyword Ranking

**Manual test via Python:**
```python
from crm.knowledge_service import search_docs, rank_answers

result = search_docs("I forgot my password and can't log in", channel="email")
print(f"confidence: {result['confidence']}")
print(f"section:    {result['section']}")
print(f"found:      {result['answer_found']}")
assert result["answer_found"] == True
assert "password_reset" in result.get("section_id", "")
print("PASS")
```

**Pass criteria:**
- `answer_found` is `True`
- `section_id` is `"password_reset"`
- `confidence` >= 0.40

---

## Test 32: Channel Adapter — WhatsApp Word Limit Enforcement

**Manual test via Python:**
```python
from channels.whatsapp_channel import send_reply

long_message = " ".join(["word"] * 200)  # 200-word message
result = send_reply("+14155552817", long_message)
sent_words = len(result["body_preview"].split())
print(f"Word count after enforcement: {result['word_count']}")
assert result["word_count"] <= 80, "FAIL: WhatsApp word limit not enforced"
print("PASS")
```

**Pass criteria:**
- Outbound message is truncated to <= 80 words

---

## Test 33: Escalation Queue Routing Accuracy

**Manual test via Python:**
```python
from crm.ticket_service import create_ticket, escalate_ticket, ESCALATION_QUEUE_MAP

test_cases = [
    ("legal_threat",    "legal-team"),
    ("refund_request",  "billing-team"),
    ("high_anger_score","senior-support"),
    ("security_incident","security-team"),
    ("enterprise_renewal","enterprise-csm"),
]

for reason, expected_queue in test_cases:
    ticket = create_ticket("C-1042", "email", f"Test: {reason}")
    ref = ticket["ticket_ref"]
    updated = escalate_ticket(ref, reason=reason)
    actual_queue = updated["escalation_queue"]
    status = "PASS" if actual_queue == expected_queue else f"FAIL (got {actual_queue})"
    print(f"{reason}: {status}")
```

**Pass criteria:**
- All 5 reason codes route to the correct specialist queue

---

## Test 34: Full End-to-End Pipeline — Debug Mode

```http
POST /support/submit
Content-Type: application/json

{
  "channel": "email",
  "customer_ref": "C-3301",
  "payload": {
    "from_email": "j.whitfield@techbridge.com",
    "from_name": "James Whitfield",
    "subject": "SSO redirect loop",
    "body": "Hello Team,\n\nWe have set up Okta SSO but when users try to log in they get stuck in a redirect loop. We are on the Business plan. Can you help?\n\nThank you,\nJames"
  },
  "debug": true
}
```

**Pass criteria:**
- Returns 200
- `data.pipeline_stages` is present (debug mode)
- `pipeline_stages.normalize.status` is `"ok"`
- `pipeline_stages.identify_customer.customer_ref` is `"C-3301"`
- `pipeline_stages.agent.status` is `"ok"`
- `pipeline_stages.ticket.ticket_ref` matches `data.ticket_ref`
- `data.kb_section` references SSO
- `data.should_escalate` is `false` (SSO is handleable)
- Full pipeline completes in < 2000ms

---

## Running All Tests

### Via HTTPie (CLI)
```bash
# Install: pip install httpie
http POST localhost:8000/support/submit channel=email payload:='{"from_email":"marcus.chen@acme.io","from_name":"Marcus","subject":"Password reset","body":"I forgot my password"}'
```

### Via curl
```bash
curl -X POST http://localhost:8000/support/submit \
  -H "Content-Type: application/json" \
  -d '{"channel":"email","payload":{"from_email":"marcus.chen@acme.io","from_name":"Marcus","subject":"Password reset","body":"I forgot my password"}}'
```

### Via Python requests
```python
import requests

BASE_URL = "http://localhost:8000"

response = requests.post(f"{BASE_URL}/support/submit", json={
    "channel": "email",
    "customer_ref": "C-1042",
    "payload": {
        "from_email": "marcus.chen@acme.io",
        "from_name": "Marcus Chen",
        "subject": "Password reset needed",
        "body": "Hello, I need to reset my password."
    }
})

print(response.status_code)
print(response.json()["data"]["ticket_ref"])
```

### Interactive Docs
Visit `http://localhost:8000/docs` for the FastAPI Swagger UI with all endpoints, schemas, and a built-in request runner.

---

## Stage 2 Test Completion Checklist

| Scenario | Status |
|---|---|
| Ticket creation via all 3 channels | Testable via Tests 2, 3, 4 |
| Customer identification (ref, email, guest) | Tests 2, 11, 27, 28 |
| AI agent KB response (confidence >= 0.40) | Tests 2, 4, 31 |
| Tier 1 immediate escalation (legal, security, refund) | Tests 5, 17, 19 |
| Tier 1 profanity escalation | Test 20 |
| Tier 2 VIP escalation | Test 15 |
| Tier 3 low KB confidence escalation | Test 21 |
| Multi-turn conversation continuity | Test 16 |
| Manual escalation via API | Test 9 |
| Human agent reply | Test 10 |
| Ticket status transitions | Tests 7, 29 |
| SLA deadline assignment by plan | Test 30 |
| Metrics tracking | Tests 22, 23, 24 |
| Error handling (404, 400, 422) | Tests 12, 13, 25, 26 |
| Channel word limits (WhatsApp <= 80 words) | Tests 3, 17, 32 |
| Escalation queue routing | Test 33 |
| Full pipeline debug mode | Test 34 |
