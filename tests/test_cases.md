# Edge Case Test Cases – Customer Success AI Agent
## NovaSync / SyncFlow | Stage 1 Prototype

**Total Cases:** 25
**Purpose:** Validate agent behavior on boundary conditions, unexpected inputs, and emotionally charged scenarios that stress-test core logic.

---

## Format

Each test case includes:
- **Input:** Message, channel, customer_id, topic
- **Expected Behavior:** What the agent should do
- **Pass Criteria:** Observable output that confirms correct handling
- **Risk if Failed:** What goes wrong if the agent handles this incorrectly

---

## Category 1: Empty & Malformed Messages

### TC-001: Completely Empty Message
**Input:**
```
message: ""
channel: "whatsapp"
customer_id: "C-2817"
topic: None
```
**Expected Behavior:** Return a clarification request asking the customer to describe their issue. Do NOT crash or return an error.

**Pass Criteria:** Response is a short, friendly WhatsApp message: "Hey! Looks like your message was empty. What can we help you with?"

**Risk if Failed:** Unhandled exception visible to customer; breaks ticket creation pipeline.

---

### TC-002: Whitespace-Only Message
**Input:**
```
message: "   \n\n\t  "
channel: "email"
customer_id: "C-1042"
topic: None
```
**Expected Behavior:** Treat as empty message. Return email-formatted clarification request.

**Pass Criteria:** Response contains "It looks like your message came through empty" or equivalent. No crash.

**Risk if Failed:** Agent attempts KB search on whitespace; likely returns low-confidence garbage response.

---

### TC-003: Single Character Message
**Input:**
```
message: "?"
channel: "web_form"
customer_id: "C-3301"
topic: None
```
**Expected Behavior:** Insufficient context — agent asks for more information.

**Pass Criteria:** Response asks the customer to describe their issue. Does not attempt KB search.

**Risk if Failed:** Agent returns a confusing non-answer or crashes on empty KB results.

---

### TC-004: Invalid Channel
**Input:**
```
message: "how do I reset my password"
channel: "telegram"
customer_id: "C-2817"
topic: "password_reset"
```
**Expected Behavior:** Fall back to `web_form` channel processing. Log a warning internally. Do not crash.

**Pass Criteria:** Response is formatted as web_form style. No exception raised.

**Risk if Failed:** TypeError / KeyError crashes the agent; customer receives no response.

---

### TC-005: Unknown Customer ID
**Input:**
```
message: "I can't log in to my account"
channel: "email"
customer_id: "C-UNKNOWN-99999"
topic: "login_issue"
```
**Expected Behavior:** Fall back to Starter plan defaults. No personalization. Response still helpful.

**Pass Criteria:** Agent returns a valid email response with standard password reset instructions. No crash. Customer not addressed by name.

**Risk if Failed:** Agent crashes or returns an empty personalized greeting with "None" visible.

---

## Category 2: Angry & Emotionally Charged Customers

### TC-006: Extreme Anger with ALL CAPS
**Input:**
```
message: "THIS IS A COMPLETE DISASTER. I HAVE BEEN WAITING 5 DAYS. YOUR PRODUCT IS BROKEN AND YOUR SUPPORT IS USELESS!!!"
channel: "whatsapp"
customer_id: "C-3356"
topic: "angry_customer"
```
**Expected Behavior:** Immediate escalation. Short de-escalation acknowledgment. No attempt to answer the underlying issue.

**Pass Criteria:**
- `should_escalate=True`
- `escalation_reason` ∈ ("high_anger_score", "excessive_caps")
- `priority` ∈ ("high", "critical")
- Response ≤80 words (WhatsApp limit)
- Response contains empathetic language, not a technical answer

**Risk if Failed:** Agent attempts to answer a vague complaint with a generic response, making the customer angrier.

---

### TC-007: Profanity in Message
**Input:**
```
message: "This shit hasn't worked for two weeks. What the hell is wrong with you people?"
channel: "whatsapp"
customer_id: "C-5103"
topic: "angry_customer"
```
**Expected Behavior:** Immediate escalation due to profanity detection.

**Pass Criteria:**
- `profanity_detected=True`
- `should_escalate=True`
- `escalation_reason="profanity_detected"`
- Response is de-escalating and human

**Risk if Failed:** Agent produces a cheerful helpdesk response that completely ignores the emotional state.

---

### TC-008: Frustrated but Resolvable Issue
**Input:**
```
message: "I've been trying to fix this OAuth error for hours and I'm getting nowhere"
channel: "email"
customer_id: "C-1134"
topic: "integration_oauth_error"
```
**Expected Behavior:** Frustration detected (not anger). Agent acknowledges, then answers. Does NOT escalate.

**Pass Criteria:**
- `sentiment="frustrated"`
- `should_escalate=False`
- Response opens with empathy sentence
- Response includes OAuth troubleshooting steps
- `kb_confidence` ≥ 0.40

**Risk if Failed:** Over-escalation wastes human agent time on an issue the AI could resolve.

---

### TC-009: Anger Score Just Below Escalation Threshold
**Input:**
```
message: "I'm really frustrated. This keeps breaking and I don't know why."
channel: "web_form"
customer_id: "C-4451"
topic: "workflow_not_triggering"
```
**Expected Behavior:** Frustration detected, anger below threshold. Agent attempts resolution first.

**Pass Criteria:**
- `anger_score` < 0.75
- `should_escalate=False`
- Response validates frustration in one sentence, then provides troubleshooting steps

**Risk if Failed:** False-positive escalation degrades performance metrics and delays resolution.

---

### TC-010: Escalation Mid-Conversation
**Input:**
```
message: "Still not working. I give up. This is hopeless."
channel: "email"
customer_id: "C-4451"
conversation_history: [
    {"role": "customer", "message": "My workflow isn't triggering", "sentiment": "neutral"},
    {"role": "agent", "message": "Please check that the workflow is set to Active", "sentiment": "N/A"},
    {"role": "customer", "message": "I already checked that. Still nothing.", "sentiment": "frustrated"},
    {"role": "agent", "message": "Let me check some other possibilities...", "sentiment": "N/A"},
]
topic: "workflow_not_triggering"
```
**Expected Behavior:** 4 turns in, still unresolved. Escalate due to `conversation_turn ≥ 4`.

**Pass Criteria:**
- `should_escalate=True`
- `escalation_reason="unresolved_after_multiple_turns"`
- Response acknowledges the ongoing issue and sets expectation for human follow-up

**Risk if Failed:** Agent loops indefinitely suggesting the same fixes, destroying the customer relationship.

---

## Category 3: Pricing, Legal, and Sensitive Topics

### TC-011: Direct Refund Request
**Input:**
```
message: "I want a full refund. This product hasn't worked and I've been charged for 2 months."
channel: "email"
customer_id: "C-5103"
topic: "refund_request"
```
**Expected Behavior:** Immediate Tier 1 escalation. Agent acknowledges and routes to billing team.

**Pass Criteria:**
- `should_escalate=True`
- `escalation_reason="refund_request"`
- `priority` ∈ ("high", "critical")
- `assigned_queue="billing-team"` in MCP escalation tool response
- Agent does NOT attempt to offer or process the refund

**Risk if Failed:** Agent promises a refund it cannot process, creating false expectations.

---

### TC-012: Pricing Negotiation
**Input:**
```
message: "Can you give me a 30% discount if I commit to an annual plan?"
channel: "whatsapp"
customer_id: "C-6229"
topic: "pricing_negotiation"
```
**Expected Behavior:** Immediate escalation to sales team. Agent does not quote prices or offer discounts.

**Pass Criteria:**
- `should_escalate=True`
- `assigned_queue="sales-team"`
- Agent response does not mention specific pricing or discount percentages

**Risk if Failed:** Agent either promises a discount (unauthorized) or quotes wrong pricing, damaging revenue or trust.

---

### TC-013: Legal Threat
**Input:**
```
message: "I will be involving my lawyer if this is not resolved today. You are in breach of your SLA."
channel: "email"
customer_id: "C-5103"
topic: "legal_contract_issue"
```
**Expected Behavior:** Immediate escalation to legal team. Agent does not respond to legal merits.

**Pass Criteria:**
- `should_escalate=True`
- `escalation_reason="legal_threat"` or `"legal_contract_issue"`
- `priority="critical"`
- Agent response is professional acknowledgment only — no admission of fault or denial

**Risk if Failed:** Agent makes statements that could be interpreted as legal admissions or denials.

---

### TC-014: GDPR Data Deletion Request
**Input:**
```
message: "Under GDPR Article 17, I am requesting immediate deletion of all my personal data from your systems."
channel: "email"
customer_id: "C-4467"
topic: "gdpr_compliance"
```
**Expected Behavior:** Immediate escalation to legal/compliance team. Agent acknowledges the right but does not process the deletion.

**Pass Criteria:**
- `should_escalate=True`
- `priority="high"`
- Response acknowledges the right, confirms it will be handled, provides expected timeline (30 days)
- Agent does NOT confirm data has been deleted

**Risk if Failed:** Agent attempts to process the deletion, which it has no authority or capability to do.

---

## Category 4: Multi-Message Conversations

### TC-015: Follow-Up After Partial Resolution
**Input:**
```
message: "The password reset email still hasn't arrived after 30 minutes"
channel: "email"
customer_id: "C-1042"
conversation_history: [
    {"role": "customer", "message": "I can't log in to my account", "sentiment": "neutral"},
    {"role": "agent", "message": "I've sent a password reset link to your email. Should arrive in 2 minutes.", "sentiment": "N/A"}
]
topic: "password_reset"
```
**Expected Behavior:** Recognize this is a follow-up on a prior resolution attempt. Provide next-level troubleshooting (check spam, try alternate email).

**Pass Criteria:**
- Response addresses "still not received" — does not repeat the original instruction
- Suggests spam folder check and alternate email verification
- `conversation_turn=2`

**Risk if Failed:** Agent gives the same "check your inbox" answer twice, infuriating the customer.

---

### TC-016: Customer Provides Clarification After Initial Ambiguity
**Input:**
```
message: "it's my Salesforce one"
channel: "whatsapp"
customer_id: "C-4357"
conversation_history: [
    {"role": "customer", "message": "my integration broke", "sentiment": "neutral"},
    {"role": "agent", "message": "Which integration is having trouble?", "sentiment": "N/A"}
]
topic: None
```
**Expected Behavior:** Use conversation history to understand "Salesforce integration broke." Provide relevant OAuth reconnection steps.

**Pass Criteria:**
- Topic resolved to Salesforce integration issue
- KB searches for Salesforce/OAuth content
- Response includes reconnection steps

**Risk if Failed:** Agent treats "it's my Salesforce one" as a standalone message and returns "I don't understand your question."

---

## Category 5: Channel Behavior Validation

### TC-017: Same Answer — Email vs. WhatsApp Format
**Input A (Email):**
```
message: "How do I reset my password?"
channel: "email"
customer_id: "C-1042"
topic: "password_reset"
```

**Input B (WhatsApp):**
```
message: "how do i reset password"
channel: "whatsapp"
customer_id: "C-2817"
topic: "password_reset"
```

**Expected Behavior:** Both resolve to the same KB section. Formatting should be dramatically different.

**Pass Criteria:**
- Email response: ≥100 words, formal greeting, numbered steps, closing
- WhatsApp response: ≤80 words, casual greeting, condensed instructions
- Both responses are factually identical on the core steps

**Risk if Failed:** Channel adaptation not working — customers receive inappropriately formatted messages.

---

### TC-018: Response Length Enforcement — WhatsApp Over Limit
**Input:**
```
# Generate a very long raw response and verify truncation
message: "Can you explain all the differences between Starter, Growth, Business, and Enterprise plans?"
channel: "whatsapp"
customer_id: "C-2817"
topic: "plan_comparison"
```
**Expected Behavior:** Response is capped at 80 words with "..." trailing if truncated. Agent does not produce a wall of text on WhatsApp.

**Pass Criteria:**
- `word_count` ≤ 80
- Response ends with "..." if content was truncated
- Most important information appears first (not cut off)

**Risk if Failed:** Customer receives a 400-word WhatsApp message — terrible UX that damages brand.

---

## Category 6: Special Scenarios

### TC-019: VIP Customer with Moderate Frustration
**Input:**
```
message: "I'm getting a bit frustrated — this should have been fixed by now"
channel: "email"
customer_id: "C-6229"
topic: "ui_bug"
```
**Expected Behavior:** Lena Hoffmann is a VIP customer. Even moderate frustration from a VIP triggers escalation (Tier 2).

**Pass Criteria:**
- `is_vip=True` detected from customer history
- `should_escalate=True`
- `escalation_reason="vip_customer_negative_sentiment"`
- Response is warm, personal, sets expectation for senior agent follow-up

**Risk if Failed:** VIP customer treated as standard customer; receives generic response; potential churn of a high-value account.

---

### TC-020: Enterprise Churn Threat
**Input:**
```
message: "We are evaluating alternatives. Unless this is fixed this week, we will be moving to a competitor."
channel: "email"
customer_id: "C-8901"
topic: "cancellation_churn_risk"
```
**Expected Behavior:** Immediate Tier 1 escalation. Route to CSM retention team. Do not attempt to retain with discounts or promises.

**Pass Criteria:**
- `should_escalate=True`
- `assigned_queue="csm-retention"` or `"enterprise-csm"`
- Response acknowledges urgency, commits to follow-up within SLA
- Agent does NOT make product or pricing commitments

**Risk if Failed:** Agent responds with a helpdesk answer to what is a relationship crisis; customer churns.

---

### TC-021: Repeat Issue Same Customer
**Input:**
```
message: "API rate limit again. This is the third time this month."
channel: "email"
customer_id: "C-4451"
topic: "api_rate_limit"
conversation_history: []
```
**Expected Behavior:** `get_customer_history` reveals 2 prior tickets with topic "api_rate_limit". Escalate due to repeated issue pattern. Do not give the same answer a third time.

**Pass Criteria:**
- Agent escalates with reason related to repeated issue
- OR agent acknowledges the recurring nature and proactively suggests a plan upgrade
- Does not give the identical "check your rate limit" answer again

**Risk if Failed:** Customer receives the same boilerplate answer for the third time; major CSAT damage.

---

### TC-022: Feature Request with Delivery Commitment Ask
**Input:**
```
message: "When will you support inbound email triggers in Gmail? I need this by Q2."
channel: "web_form"
customer_id: "C-1013"
topic: "feature_request"
```
**Expected Behavior:** Escalate — customer is asking for a feature delivery commitment which the agent cannot make.

**Pass Criteria:**
- `should_escalate=True`
- Agent does NOT commit to a delivery date
- Agent does NOT say "this is not on our roadmap" (unauthorized product disclosure)
- Response routes to product team or CSM

**Risk if Failed:** Agent either promises a feature date (unauthorized) or dismisses the request, harming the relationship.

---

### TC-023: Security Documentation Request (Enterprise)
**Input:**
```
message: "We need your SOC 2 Type II report and penetration test summary for our vendor review."
channel: "email"
customer_id: "C-4457"
topic: "security_documentation"
```
**Expected Behavior:** Escalate to enterprise CSM. These documents require NDA review before sharing.

**Pass Criteria:**
- `should_escalate=True`
- `assigned_queue` ∈ ("enterprise-csm", "security-team")
- Agent does NOT share or promise to send the documents
- Response acknowledges the request and sets expectation for proper process

**Risk if Failed:** Agent claims documents don't exist, or worse, attempts to attach sensitive files.

---

### TC-024: Multi-Issue Single Message
**Input:**
```
message: "Two things: first my API key stopped working, and second I got an unexpected charge on my invoice this month."
channel: "email"
customer_id: "C-1042"
topic: None
```
**Expected Behavior:** Identify two distinct issues. Address the primary (API key) and acknowledge the secondary (billing). Flag billing for follow-up or include billing answer if KB has it.

**Pass Criteria:**
- Response addresses both issues
- API key resolution appears first (technical, resolvable)
- Billing explanation included (KB has prorated charge answer)
- Single coherent email, not two separate responses

**Risk if Failed:** Agent addresses only one issue; customer must write back again; increases ticket count unnecessarily.

---

### TC-025: Non-English Message
**Input:**
```
message: "Comment puis-je réinitialiser mon mot de passe?"
channel: "web_form"
customer_id: "C-3235"
topic: None
```
**Expected Behavior:** Agent detects non-English content. Cannot serve in French (Stage 1 limitation). Escalates gracefully.

**Pass Criteria:**
- Agent does not attempt to answer in English assuming the customer will understand
- Response acknowledges the language limitation
- Ticket is escalated or routed to a human who can handle French support
- OR agent provides a translated response (if multilingual capability is available)

**Risk if Failed:** Customer receives an English response they cannot understand; CSAT failure; potentially lost customer.

---

## Test Execution Summary

| Category | Cases | Critical Priority |
|----------|-------|-------------------|
| Empty / Malformed | 5 | TC-001 (empty crash), TC-004 (invalid channel) |
| Angry / Emotional | 5 | TC-006 (extreme anger), TC-007 (profanity) |
| Pricing / Legal | 4 | TC-011 (refund), TC-012 (pricing), TC-013 (legal) |
| Multi-Message | 2 | TC-015 (follow-up), TC-016 (clarification) |
| Channel Format | 2 | TC-017 (format diff), TC-018 (length limit) |
| Special Scenarios | 7 | TC-019 (VIP), TC-020 (churn), TC-025 (non-English) |

**Pass threshold for Stage 1 demo:** 22 / 25 cases passing (88%)
**Must-pass cases:** TC-001, TC-006, TC-007, TC-011, TC-012, TC-013 (any failure here is a demo blocker)
