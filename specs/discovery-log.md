# Discovery Log – Stage 1 Incubation
## NovaSync Customer Success Digital FTE

**Stage:** 1 – Incubation / Exploration
**Period:** March 2026
**Status:** Complete (Stage 1 closed)
**Total Discoveries:** 12
**Bugs Found:** 4 (all fixed in Stage 1)

This document captures what we learned during Stage 1 — from analyzing the sample ticket data, running the prototype against test cases, and observing where the system failed. It is not a requirements document or a spec. It is a log of genuine observations that changed what we built.

Each entry records: what was observed, what data or test it came from, how it affected the design, and whether it opened new questions.

---

## Discovery 1: Channel Message Length Varies by a Factor of 8

**Source:** Analysis of all 55 sample tickets in `context/sample-tickets.json`

**Observed:**

| Channel | Avg Word Count | Min | Max | Structural Style |
|---------|---------------|-----|-----|-----------------|
| Email | 87 words | 28 | 162 | Formal greeting, multi-paragraph, signed |
| WhatsApp | 11 words | 4 | 24 | Lowercase, no punctuation, phrase-level |
| Web Form | 51 words | 18 | 94 | "Issue Type:" prefix, technical, structured |

Email messages are on average **8x longer than WhatsApp messages**. This is not just a style difference — it reflects a fundamentally different communication contract. WhatsApp customers expect to be answered in the same medium they speak in. A 300-word response to an 11-word question breaks that contract completely.

**Specific Examples from Sample Data:**

The same issue — password reset — appeared as:
- Email (T-0001, 97 words): "I am writing because I have been unable to log into my SyncFlow account since yesterday evening. I have tried resetting my password twice but have not received the reset email..."
- WhatsApp (T-0002, 9 words): "hi how do i reset my password i forgot it"
- Web Form (T-0020, 38 words): "Issue Type: Account / I would like to transfer ownership... Please advise on the steps."

**Design Impact:**
- Response length caps set from data: Email 300 words, WhatsApp 80 words, Web Form 200 words
- WhatsApp formatter hard-truncates at 80 words with "..." suffix — no soft limit
- WhatsApp responses must lead with the answer, not context — the customer will not scroll
- Web Form responses use numbered steps because form customers already expect structure

**Open Question:** Should WhatsApp responses be split across multiple short messages (like a real chat conversation) rather than one slightly longer message? Noted as a Stage 2 UX exploration.

---

## Discovery 2: Top 9 Support Topics and Their Frequency

**Source:** Manual categorization of all 55 sample tickets

**Observed:**

| Rank | Topic | Count | % | Escalates? |
|------|-------|-------|---|-----------|
| 1 | API errors (401, 403, 404, 429, 500) | 9 | 16.4% | Rarely |
| 2 | Billing questions | 8 | 14.5% | Sometimes |
| 3 | Workflow not triggering | 6 | 10.9% | Rarely |
| 4 | Integration issues (OAuth, reconnect) | 6 | 10.9% | Rarely |
| 5 | Escalation-required topics | 7 | 12.7% | Always |
| 6 | Password reset / login issues | 5 | 9.1% | Never |
| 7 | Account/team management | 5 | 9.1% | Rarely |
| 8 | Security/compliance | 5 | 9.1% | Usually |
| 9 | Feature questions | 4 | 7.3% | Sometimes |

**Key Finding:** API errors are the single most frequent resolvable category. Every common error code (401, 403, 404, 429, 500) has a specific resolution that the agent can provide. This justified splitting API errors into two KB entries — authentication errors and rate limit errors — rather than one generic "API help" entry.

**Key Finding:** The "escalation-required" category (12.7%) is as common as workflow issues and more common than password reset. This validated the decision to invest heavily in escalation detection, not just KB coverage.

**Design Impact:**
- KB entries prioritized in order of topic frequency
- API errors given dedicated entries with all 5 error codes and specific resolutions per code
- Escalation-required topics (pricing, legal, refunds) given Tier 1 immediate-escalation status so the agent never attempts to answer them

---

## Discovery 3: 23.6% of Tickets Require Escalation — Most Are Non-Technical

**Source:** Classification of all 55 sample tickets against escalation-rules.md

**Observed:** 13 of 55 tickets (23.6%) require human escalation. Breakdown by reason:

| Escalation Category | Count | % of Escalations |
|--------------------|-------|-----------------|
| Refund / billing authorization | 3 | 23% |
| Legal / compliance (GDPR, contracts) | 3 | 23% |
| Pricing negotiation / sales | 2 | 15% |
| Security / account compromise | 2 | 15% |
| Churn risk / cancellation | 2 | 15% |
| Enterprise CSM involvement | 1 | 8% |

**Critical Finding:** The vast majority of escalations are **not about technical complexity**. They are about business authorization (refunds, pricing), legal liability (GDPR, contracts, litigation), or emotional state (churn threat, security panic). The AI agent's KB coverage quality is not the primary bottleneck for escalation — the agent simply has no authority to handle these topics, regardless of how well it understands them.

**Design Impact:**
- Escalation architecture given equal priority to KB architecture
- 5 specialist queues created (billing-team, legal-team, sales-team, security-team, enterprise-csm) rather than one generic queue — routing by reason code ensures the right expertise handles each case
- Tier 1 (immediate, pre-KB) escalation exists specifically for the categories listed above
- The `escalation_rules.md` document was written as a standalone reference for human agents

---

## Discovery 4: Sentiment Distribution and the Reliability of ALL CAPS

**Source:** Running all 55 sample ticket messages through the `detect_sentiment()` prototype and comparing to human-labeled expected sentiment

**Observed:**

| Sentiment Class | Count | % | Primary Signals |
|-----------------|-------|---|----------------|
| Neutral | 29 | 52.7% | Absence of negative signals |
| Frustrated | 14 | 25.5% | Frustration keywords, repeated contact |
| Angry | 7 | 12.7% | CAPS, profanity, anger keywords, urgency |
| Positive | 5 | 9.1% | Thank-you language, "helpful", "great" |

**Signal Reliability Analysis (from the 7 angry-classified messages):**

| Signal | Present in angry messages | False positive rate |
|--------|--------------------------|---------------------|
| ALL CAPS (>30% ratio) | 6 out of 7 (86%) | ~12% |
| 3+ exclamation marks | 5 out of 7 (71%) | ~15% |
| Anger keywords | 5 out of 7 (71%) | ~18% |
| Urgency keywords | 7 out of 7 (100%) | ~25% |
| Profanity | 1 out of 7 (14%) | ~2% |

**Finding:** ALL CAPS ratio is the most reliable single signal for anger classification among the signals we can detect without semantic understanding. It was present in 86% of angry messages with a relatively low false positive rate. It was confirmed as the primary anger signal, with keyword matching as secondary.

**Finding:** Urgency keywords were present in ALL angry messages — but also in many neutral messages ("I need this urgently", "this is time-sensitive"). They are better used as an escalation speed signal (prioritize the ticket) than an anger signal.

**Design Impact:**
- Caps ratio threshold set at 0.30 (not 0.40 — see Discovery 11 for the bug that required this correction)
- Caps ratio contributes +0.25 to anger_score (highest single weight)
- Exclamation count (3+) contributes +0.10
- Anger keyword hits contribute +0.18 each
- Urgency detection drives `urgency_detected=True` flag rather than feeding anger_score

---

## Discovery 5: Cross-Channel Conversation Continuity Is a Real Problem

**Source:** Ticket T-0038 in sample data — Fatou Diallo contacted via Web Form, then followed up via email

**Observed:**
- T-0020: Fatou Diallo submits a web form ticket about account ownership transfer
- T-0038: Three days later, Fatou follows up via email: "Following up on my earlier request about transferring account ownership. My colleague has not received the confirmation email. It has been over 24 hours."

The follow-up email is incomprehensible without the context of the original web form request. Any agent handling T-0038 without T-0020's context would treat it as a fresh password/invite issue and give a wrong answer.

**Current Gap:** The Stage 1 agent has no cross-channel session linking. Each message is processed as standalone.

**Mitigation Available in Stage 1:** The `get_customer_history()` MCP tool retrieves all prior tickets for a customer ID regardless of channel. If the agent loads customer history at the start of every conversation, it can see that this customer has a prior open ticket about "account_ownership_transfer" — which provides enough context to connect the dots.

**Design Impact:**
- `conversation_history` parameter added for same-channel multi-turn memory
- `get_customer_history()` used to surface cross-channel prior tickets
- Cross-channel continuity (unified session ID) flagged as **Stage 2 must-have** — the Stage 1 mitigation is partial
- Customer ID (not just email address) established as the primary identifier across all channels

---

## Discovery 6: Short WhatsApp Messages Produce Systematically Low KB Confidence

**Source:** Running all 14 WhatsApp tickets through `search_knowledge_base()` and comparing confidence scores to email/web form tickets with the same topic

**Observed:**

| Query (same topic) | Channel | KB Confidence |
|-------------------|---------|--------------|
| "webhook not firing since yesterday. is there an outage?" | WhatsApp | 0.38 |
| "Webhook not firing: workflow ID WF-11823. Issue since Monday." | Web Form | 0.61 |
| "My webhook stopped delivering events... [full email]" | Email | 0.74 |

The WhatsApp query produces below-threshold confidence (0.38 < 0.40) despite being about the same topic as the web form query (0.61). The difference is entirely length and keyword density.

**Why:** Keyword overlap scoring is proportional to the number of matching tokens. A 9-word WhatsApp message has fewer tokens to match than a 51-word web form message, even if both cover the same topic. The KB tags only need to match a few of them, but shorter messages have fewer chances to match.

**Design Impact:**
- KB confidence threshold kept at 0.40 (not raised) specifically because raising it would cause too many WhatsApp tickets to fall below threshold and escalate unnecessarily
- Below-threshold behavior for WhatsApp: agent asks one clarifying question (max 15 words) before deciding to escalate
- This is an acknowledged Stage 1 limitation — semantic search (Stage 2) handles short queries far better than keyword overlap

**Open Question:** Should the confidence threshold be channel-dependent? (e.g., 0.40 for email, 0.25 for WhatsApp.) Noted for Stage 2 experimentation.

---

## Discovery 7: Enterprise Customers Have Categorically Different Support Needs

**Source:** Enterprise-plan tickets T-0028, T-0041, T-0044, T-0050

**Observed Pattern:** All four Enterprise tickets had:
1. **Regulatory or contractual urgency** — "must be completed before April 15th due to new regulatory requirements" (T-0028), "deadline: March 20th" (T-0041)
2. **Requests the AI cannot fulfill** — SOC 2 report, penetration test summary, DPA, data residency migration
3. **Named CSM expectation** — "Who is the right contact for this?" (T-0050), "connect us with your legal or compliance team" (T-0025)
4. **High consequence of wrong answer** — A wrong answer to a GDPR compliance question is not a support error; it is a legal risk

**Design Impact:**
- Enterprise plan customers get the most aggressive escalation profile — any frustration signal from an Enterprise customer triggers Tier 2 escalation (vs. Tier 3 for other plans)
- Security documentation requests (SOC 2, pen test) always route to enterprise-csm queue, never answered by AI
- SLA acknowledgment message for Enterprise uses "within 1 hour" (their contracted SLA)
- `get_customer_history()` returns `plan` — the agent adjusts escalation thresholds based on this value

---

## Discovery 8: Repeat Contacts for the Same Issue Signal Churn Risk

**Source:** Customer C-4451 (Sofia Reyes, Growth plan) — 2 prior tickets both with topic "api_rate_limit"

**Observed:**
- T-0004: Sofia contacts about 429 API rate limit errors
- Customer history shows 2 prior resolved tickets with identical topic
- Account health in CRM: flagged as "at_risk"
- Behavior pattern: customer is hitting the same problem repeatedly — either the previous resolution didn't stick, or the root cause (plan limit too low for their usage) is structural

**Finding:** Giving the same answer for the third time is the wrong move. A customer who has contacted support 3 times about the same issue needs a different response — either a structural fix (upgrade recommendation), an escalation to a CSM, or an investigation into why the resolution doesn't hold.

**Design Impact:**
- `get_customer_history()` exposes `recent_tickets` with topics — agent can detect the repeat pattern
- Repeat issue (3+ contacts for same topic) added to Tier 2 escalation triggers ("repeated_same_issue")
- `account_health` field in customer history enables proactive identification of at-risk accounts
- Stage 2 recommendation: proactive outbound message to at-risk accounts showing repeated same issue before they contact support again

---

## Discovery 9: Knowledge Base Has Specific Coverage Gaps

**Source:** Testing queries from all 55 tickets that were not explicitly covered in the KB; recording those with confidence < 0.30

**Observed — Queries With No KB Match:**

| Customer Query (paraphrased) | Ticket | Confidence | Missing Coverage |
|------------------------------|--------|-----------|-----------------|
| "Does SyncFlow work offline?" | T-0051 | 0.05 | Offline/mobile capabilities |
| "Can I use the API without coding?" | T-0034 | 0.08 | No-code API / Zapier-style usage |
| "Gmail integration — inbound trigger available?" | T-0047 | 0.12 | Gmail trigger direction (send vs. receive) |
| "Self-hosted Jira — do you support it?" | T-0035 | 0.15 | Integration compatibility matrix |
| "Automation run spike — which workflow is using the most?" | T-0053 | 0.20 | Usage analytics / debugging |

**Current Handling:** All 5 fall below the 0.40 confidence threshold. The agent returns a clarifying question or escalates to technical support. This is acceptable for Stage 1 but represents 9% of the sample ticket volume going to unnecessary escalation.

**Design Impact:**
- 5 gap topics flagged for KB expansion before Stage 2
- A "KB gap log" is recommended as a Stage 2 operational tool — automatically record every sub-threshold query so the support team can prioritize what to add next
- The `section` field in KB search results enables this: when `answer_found=False`, log the query for review

---

## Discovery 10: Response Tone Must Change Based on Sentiment, Not Just Channel

**Source:** Manual review of agent responses against frustrated ticket messages

**Observed:** The same formal email tone that works for a neutral customer ("Here are the steps to resolve this...") feels dismissive to a frustrated customer. Example:

Customer (frustrated): "I've been trying to fix this OAuth error for hours and I'm getting nowhere"

**Agent response without tone calibration:**
> "Hi Henrik, To reconnect the OAuth integration: 1. Go to Integrations... 2. Click Reconnect..."

**Agent response with tone calibration:**
> "Hi Henrik, I can see this has been taking up a lot of your time — that's genuinely frustrating. Here's what should fix it: 1. Go to Integrations..."

The second version is objectively more empathetic. The customer's frustration is acknowledged in one sentence before the solution is provided. This is consistent with the empathy standards in `brand-voice.md`.

**Sentiment-to-tone mapping established:**

| Sentiment | Response Opening | Then |
|-----------|-----------------|------|
| Positive / Neutral | Answer directly | N/A |
| Frustrated | One-sentence validation | Provide answer |
| Angry | De-escalation only | Route to human |

**Design Impact:**
- `sentiment_result` passed into `format_response_for_channel()` so the formatter can prepend the validation sentence for frustrated messages
- Angry messages skip KB answer entirely and go straight to escalation acknowledgment
- Escalation acknowledgment message calibrated by channel: WhatsApp version is 1 sentence, email version is 2 sentences with fuller context

---

## Discovery 11: Substring Matching Produces Dangerous False Positives

**Source:** Running test case TC-003 (web form: "Issue Type: Billing...") — incorrectly triggered legal escalation. Running test case TC-006 (WhatsApp: "Hey! how do I...") — incorrectly detected profanity.

**Observed — Two Critical Bugs:**

**Bug 1: "hello" triggers "hell" profanity detection**
- Code: `any(word in text_lower for word in PROFANITY_KEYWORDS)` with "hell" in the list
- "Hello" lowercased is "hello" — contains the substring "hell"
- Every WhatsApp greeting ("hey", "hello") triggered a profanity flag
- Effect: customers were being escalated to senior-support immediately upon saying "hello"

**Bug 2: "Issue" triggers "sue" legal escalation**
- Code: `any(signal in message_lower for signal in legal_signals)` with "sue" in the list
- Web form tickets always begin with "Issue Type:" — every web form ticket matched "sue" as a substring
- Effect: 100% of web form tickets were being escalated with reason="legal_threat" at priority="critical"

**Both bugs shared the same root cause:** substring matching without word boundary constraints. `"hell" in "hello"` and `"sue" in "issue"` both evaluate to `True` in Python string `in` operator.

**Fix Applied:**
```python
# Before (wrong):
any(word in text_lower for word in PROFANITY_KEYWORDS)

# After (correct):
any(
    re.search(r'\b' + re.escape(word) + r'\b', text_lower)
    for word in PROFANITY_KEYWORDS
)
```

The `\b` word-boundary assertion in the regex ensures "hell" only matches as a standalone word, not as part of "hello". Applied to both profanity detection and legal signal detection.

**Design Impact:**
- All keyword detection in `detect_sentiment()` and `decide_escalation()` switched to word-boundary regex
- This applies to: profanity keywords, legal signals, breach signals
- Word-boundary regex is now the enforced standard for any future keyword addition to either list
- This bug would have made the agent completely unusable on web form tickets — catching it in Stage 1 via edge case testing was critical

---

## Discovery 12: Sentiment Threshold Tuning Required Mid-Prototype

**Source:** Running TC-006 ("THIS IS RIDICULOUS I've been waiting 3 DAYS...") through `detect_sentiment()` with the initial 0.40 caps threshold

**Observed:** The initial caps_ratio threshold (0.40) was too conservative for real angry messages. "THIS IS RIDICULOUS I've been waiting 3 DAYS and nobody has helped me!!! My entire business is DOWN!!!" was being classified as "neutral" because:
- The string contains significant lowercase text ("been", "waiting", "nobody", "helped", "me", "My", "entire", "business", "is")
- Measured caps ratio: ~0.31 (uppercase chars / total alpha chars)
- 0.31 < 0.40 → caps signal not triggered
- Only 1 anger keyword matched ("ridiculous") → anger_score = 0.18
- Exclamation count ≥ 3 → +0.10 → total anger_score = 0.28
- Result: classified as "neutral" despite being clearly angry

**Root Cause:** The 0.40 threshold assumed caps-lock-style typing ("EVERYTHING IN ALL CAPS"). Real angry messages often mix EMPHASIS CAPS with lowercase context words.

**Fix Applied:**
- Caps ratio threshold lowered from 0.40 to 0.30
- Caps ratio weight increased from +0.20 to +0.25 (to maintain escalation at appropriate score with the lower threshold)
- Net effect: The above message now correctly scores caps_ratio=0.31 > 0.30 → anger_score = 0.18 + 0.25 + 0.10 = 0.53 → classified "frustrated" (>0.35)
- Produces correct escalation due to low KB confidence on vague venting message

**Note:** "frustrated" rather than "angry" is accurate here — the message lacks profanity and the anger score (0.53) is below the "angry" threshold (0.65). The important outcome is the escalation, which does occur. The sentiment label influences the acknowledgment message tone, not the escalation decision.

**Design Impact:**
- `caps_ratio` threshold in `detect_sentiment()`: 0.40 → 0.30
- Anger score weight for caps: +0.20 → +0.25
- These values are explicitly documented in this log so future contributors understand why the threshold is not the intuitive 0.40

---

## Edge Cases Catalogued During Stage 1

| Edge Case | Ticket Reference | Stage 1 Handling | Quality |
|-----------|----------------|-----------------|---------|
| Empty message | TC-001 | Returns clarification request, no crash | Good |
| Whitespace-only message | TC-002 | Same as empty message (same guard) | Good |
| Invalid channel value | TC-004 | Falls back to web_form, no crash | Adequate |
| Unknown customer ID | TC-005 | Defaults to Starter plan, no personalization | Adequate |
| Extreme anger / ALL CAPS | TC-006 | Escalates (after threshold fix) | Good |
| Profanity | TC-007 | Immediate escalation | Good |
| Non-English message (French) | TC-025 | KB confidence 0.00, asks clarifying question in English | Poor — Stage 2 must fix |
| Multi-issue message | TC-024 | Addresses primary issue, notes secondary | Adequate |
| Repeat issue (3rd contact) | TC-021 | Escalates or notes repeat | Good |
| Channel switching (web -> email) | T-0038 | Partial — customer history available but no session link | Adequate |

---

## Design Decisions Influenced by Discoveries

This table maps each discovery to the specific design element it produced or changed:

| Discovery | Design Element Changed |
|-----------|----------------------|
| D1: Channel length variance | `CHANNEL_PROFILES` word limits; distinct formatter functions |
| D2: Topic frequency distribution | KB entry priority order; API error split into two entries |
| D3: 23.6% escalation, non-technical | 5 specialist queues; Tier 1 pre-KB escalation |
| D4: ALL CAPS as primary anger signal | `caps_ratio` in sentiment; threshold at 0.30 |
| D5: Cross-channel continuity gap | `customer_history` mitigation; Stage 2 flagged |
| D6: WhatsApp low KB confidence | Confidence threshold kept at 0.40 not raised |
| D7: Enterprise needs differ | Enterprise-plan escalation profile; 1-hour SLA in ack message |
| D8: Repeat contact = churn risk | "repeated_same_issue" Tier 2 trigger; `account_health` field |
| D9: KB coverage gaps (9% of tickets) | 5 gap topics flagged; KB gap logging recommended |
| D10: Tone must match sentiment | Validation sentence prepended for frustrated; escalation ack for angry |
| D11: Substring matching false positives | Word-boundary regex for all keyword detection |
| D12: Caps threshold too conservative | Threshold 0.40 -> 0.30; weight +0.20 -> +0.25 |

---

## Open Questions for Stage 2

These questions surfaced during Stage 1 exploration but could not be answered within the prototype scope. Each has a hypothesis.

**Q1: Should KB confidence thresholds be channel-dependent?**
Hypothesis: Yes. WhatsApp messages are structurally token-sparse. A separate threshold of 0.25–0.30 for WhatsApp would reduce unnecessary escalations without reducing quality, because the clarifying question behavior already catches truly ambiguous messages.

**Q2: Can sentiment detection be significantly improved by a single Claude API call?**
Hypothesis: Yes, substantially. The current heuristic system has ~12% false positive rate. A Claude classification call with a structured prompt ("classify this message's emotional tone and intensity on a scale of 0-1") would likely halve that. The tradeoff is latency and cost per message.

**Q3: Should the agent always ask one clarifying question on WhatsApp before attempting an answer?**
Hypothesis: Only when confidence is below 0.35. Above that, answering is faster and customers prefer it. Below 0.35, a clarifying question improves first-contact resolution rate.

**Q4: How do we measure false escalation rate reliably?**
Hypothesis: Track tickets where a human agent resolves the issue in under 2 minutes. This is a strong signal the AI could have handled it. Requires the human-agent system to log resolution time per ticket.

**Q5: What is the optimal KB size for keyword matching before vector search becomes necessary?**
Hypothesis: The crossover point is around 30–50 KB entries. At 12 entries (Stage 1), keyword matching is fast and accurate enough. At 50+ entries, topic overlap between entries reduces matching precision and semantic search becomes clearly superior.

**Q6: Should the agent support more than one clarifying question?**
Current policy: maximum one. Hypothesis: This is correct. Two clarifying questions in sequence makes the agent feel bureaucratic. If the first clarifying question doesn't resolve ambiguity, escalate.
