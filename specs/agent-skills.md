# Agent Skills Manifest – Customer Success AI Agent

**Agent Name:** SyncBot
**System:** NovaSync Customer Success Digital FTE
**Version:** 1.0.0 (Stage 1 Prototype)
**Last Updated:** March 2026

---

## Overview

SyncBot is a digital Customer Success agent that handles inbound support queries across Email, WhatsApp, and Web Form channels. This document defines each skill the agent possesses, including purpose, inputs, outputs, and usage examples.

---

## Skill 1: Knowledge Retrieval

### Purpose
Search the SyncFlow product documentation and knowledge base to find accurate, actionable answers to customer questions. This is the primary resolution mechanism.

### Description
The agent uses keyword and semantic matching to identify the most relevant sections of product documentation. It extracts actionable content and surfaces it in a format appropriate for the customer's channel.

**Stage 1:** Keyword overlap scoring against structured KB entries
**Stage 2 (planned):** Claude embeddings + vector similarity search

### Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `query` | string | Yes | The customer's question or issue description |
| `channel` | string | Yes | Channel context for length calibration |
| `customer_plan` | string | No | Plan tier — affects which features/limits to reference |
| `max_results` | int | No | Max document sections to retrieve (default: 3) |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `answer_found` | bool | Whether a satisfactory answer was located |
| `answer` | string | Extracted answer content |
| `confidence` | float 0.0–1.0 | Confidence in the retrieved answer |
| `section` | string | Source document section (e.g., "Billing → Refund Policy") |
| `snippets` | list[str] | Relevant text excerpts |

### Confidence Thresholds

| Score | Agent Behavior |
|-------|---------------|
| ≥ 0.75 | Answer directly with confidence |
| 0.40–0.74 | Answer with a caveat; offer to confirm |
| < 0.40 | Acknowledge uncertainty; escalate or ask for clarification |

### Example Usage
```python
result = search_knowledge_base(
    query="how do I reset my password",
    channel="whatsapp"
)
# Returns: section="Password & Security → Password Reset"
#          confidence=0.92, answer_found=True
```

---

## Skill 2: Sentiment Analysis

### Purpose
Detect the emotional tone of incoming customer messages to determine urgency, frustration level, and the appropriate response style. The primary input to escalation decisions.

### Description
Analyzes linguistic signals, vocabulary, punctuation patterns, and message structure to classify sentiment and produce numerical scores. Feeds directly into the escalation decision engine.

**Stage 1:** Keyword heuristics, caps ratio, exclamation analysis
**Stage 2 (planned):** Claude API structured classification call

### Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | Yes | The raw customer message |
| `conversation_history` | list[dict] | No | Prior messages for trend detection |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `sentiment` | string | "positive" / "neutral" / "frustrated" / "angry" |
| `anger_score` | float 0.0–1.0 | Anger intensity |
| `frustration_score` | float 0.0–1.0 | Frustration intensity |
| `urgency_detected` | bool | Urgency keyword present |
| `profanity_detected` | bool | Abusive language present |
| `caps_ratio` | float | Ratio of uppercase letters |
| `tone_flags` | list[str] | Signals: "excessive_caps", "exclamation_overuse", etc. |

### Escalation Triggers

| Signal | Threshold | Action |
|--------|-----------|--------|
| anger_score | ≥ 0.75 | Immediate escalation |
| frustration_score | ≥ 0.70 on 2+ messages | Escalate after attempt |
| profanity_detected | True | Immediate escalation |

### Example Usage
```python
result = detect_sentiment(
    message="THIS IS RIDICULOUS!!! 3 DAYS and nothing!!! My business is DOWN!!!",
    conversation_history=[]
)
# Returns: sentiment="angry", anger_score=0.82, urgency_detected=True,
#          tone_flags=["excessive_caps", "exclamation_overuse"]
```

---

## Skill 3: Escalation Decision

### Purpose
Evaluate whether a ticket requires human intervention. Synthesizes signals from sentiment analysis, knowledge retrieval confidence, business rules, and customer tier into a clear escalate/no-escalate decision.

### Description
Acts as the agent's judgment layer. Runs after every message exchange to decide whether the agent should continue autonomously or hand off to a human with full context.

### Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `sentiment_result` | dict | Yes | Output from Sentiment Analysis |
| `kb_result` | dict | Yes | Output from Knowledge Retrieval |
| `topic` | string | No | Classified issue topic |
| `customer` | dict | Yes | Customer profile (plan, is_vip, etc.) |
| `conversation_turn` | int | Yes | Number of exchanges so far |
| `message` | string | Yes | Raw message for keyword scanning |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `should_escalate` | bool | Escalate? |
| `reason` | string | Reason code (e.g., "high_anger_score", "refund_request") |
| `priority` | string | "critical" / "high" / "medium" / "low" |
| `tier` | int | 1 = immediate, 2 = after attempt, 3 = judgment |

### Decision Hierarchy

```
1. Tier 1 — Immediate (skip AI resolution):
   → Legal threat / security breach / large refund / contract dispute
   → Profanity / anger_score ≥ 0.75
   → Escalation-mandated topics (pricing_negotiation, account_compromise)

2. Tier 2 — After one AI attempt:
   → Frustration ≥ 0.70 on 2+ messages
   → conversation_turn ≥ 4 and unresolved
   → VIP customer with negative sentiment
   → Enterprise customer frustrated

3. Tier 3 — Judgment-based:
   → VIP with 2+ unresolved turns
   → KB confidence < 0.40
```

### Example Usage
```python
result = decide_escalation(
    sentiment_result={"anger_score": 0.82, "profanity_detected": False},
    topic="pricing_negotiation",
    customer={"plan": "business", "is_vip": False},
    conversation_turn=1,
    message="I want a discount or I'm leaving"
)
# Returns: should_escalate=True, reason="pricing_negotiation", priority="medium", tier=1
```

---

## Skill 4: Channel Adaptation

### Purpose
Format and adapt the agent's response to match the communication style, length, and structural expectations of the customer's channel. Ensures the same information feels native to each platform.

### Description
Applies channel-specific tone rules, length constraints, greeting and closing templates, and formatting conventions (bullets, numbered lists, plain prose) post-response-generation.

### Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `raw_response` | string | Yes | Generated response content |
| `channel` | string | Yes | "email" / "whatsapp" / "web_form" |
| `customer_name` | string | Yes | For personalized greeting |
| `topic` | string | No | Issue topic for email subject line |
| `is_escalation` | bool | No | Whether this is an escalation handoff message |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `response` | string | Channel-formatted final message |
| `subject_line` | string | Email subject line (email only) |
| `word_count` | int | Final word count |
| `format_type` | string | "formal" / "conversational" / "structured" |

### Channel Format Rules

| Channel | Tone | Max Words | Greeting | Bullets? | Closing? |
|---------|------|-----------|----------|----------|---------|
| email | formal | 300 | "Hi {Name}," | Yes | Yes |
| whatsapp | conversational | 80 | "Hey {Name}!" | No | No |
| web_form | semi-formal | 200 | "Hi {Name}," | Yes | Brief |

### Example Usage
```python
result = format_response_for_channel(
    raw_response="Reset password via Settings → Security → Reset Password",
    channel="whatsapp",
    customer_name="Priya"
)
# Returns: response="Hey Priya! Go to Settings → Security → Reset Password.
#                    You'll get a reset email in 2 mins 👍"
#          format_type="conversational", word_count=22
```

---

## Skill 5: Customer Identification

### Purpose
Identify and load the customer's account profile before processing their message. Enables personalization, plan-aware responses, and appropriate SLA routing.

### Description
Matches incoming sender identity (email, phone, session ID) against the CRM/customer database. Provides all contextual signals the agent needs to calibrate its response: plan tier, VIP status, account health, prior ticket history.

### Inputs

| Input | Type | Required | Description |
|-------|------|----------|-------------|
| `customer_id` | string | Yes | Internal customer identifier |
| `channel` | string | Yes | Source channel |

### Outputs

| Output | Type | Description |
|--------|------|-------------|
| `found` | bool | Whether customer was identified |
| `name` | string | Customer's display name |
| `plan` | string | Current subscription tier |
| `account_health` | string | "healthy" / "at_risk" / "churning" |
| `open_tickets` | int | Currently open ticket count |
| `recent_tickets` | list[dict] | Summary of recent support history |
| `is_vip` | bool | VIP flag |
| `mrr` | float | Monthly recurring revenue |
| `csat_average` | float | Historical customer satisfaction score |

### Fallback Behavior
If a customer cannot be identified:
1. Agent asks for their account email address
2. Provides support without personalization if they prefer anonymity
3. Ticket is flagged "unidentified" for human review

### Example Usage
```python
result = get_customer_history("C-1042")
# Returns: name="Marcus Chen", plan="growth", is_vip=False,
#          account_health="healthy", open_tickets=0, csat_average=4.6
```

---

## Skill Interaction Flow

```
INBOUND MESSAGE
      │
      ▼
[Skill 5: Customer Identification]
  Load profile, plan, VIP status
      │
      ▼
[Skill 2: Sentiment Analysis]
  Score anger, frustration, urgency
      │
      ├─── Tier 1 trigger? ──────────────────────────────────┐
      │    (legal, breach, profanity, anger ≥ 0.75)          │
      │                                                       ▼
      │                                          [Skill 3: Escalation Decision]
      ▼                                               route to human queue
[Skill 1: Knowledge Retrieval]
  Search KB, score confidence
      │
      ├─── Confidence < 0.40? ───────────────────────────────┐
      │                                                       │
      ▼                                                       ▼
[Generate Response Content]               [Skill 3: Escalation Decision]
                                               reason=low_kb_confidence
      │
      ▼
[Skill 3: Escalation Decision]
  Final check: turns, VIP, tier
      │
      ├─── Escalate? ────────────────────────────────────────┐
      │                                                       ▼
      ▼                                         Human queue + escalation msg
[Skill 4: Channel Adaptation]
  Format, length limit, greeting/closing
      │
      ▼
SEND RESPONSE → Log → Update Ticket State
```

---

## Skill Versioning

| Skill | Current Version | Stage 2 Planned Upgrade |
|-------|----------------|------------------------|
| Knowledge Retrieval | 1.0.0 (keyword) | Vector embeddings + Claude |
| Sentiment Analysis | 1.0.0 (heuristic) | Claude structured classification |
| Escalation Decision | 1.0.0 (rule-based) | ML-assisted with feedback loop |
| Channel Adaptation | 1.0.0 (template) | LLM-driven adaptive formatting |
| Customer Identification | 1.0.0 (mock CRM) | Live CRM API (Salesforce/HubSpot) |
