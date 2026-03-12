# Escalation Rules – NovaSync Customer Success Agent

## Overview

This document defines conditions under which the AI Customer Success Agent must escalate a conversation to a human support agent. The agent should always attempt autonomous resolution first. Escalation is a safety net, not a default.

---

## TIER 1 – Immediate Escalation (No AI Response First)

These situations skip AI resolution entirely and route directly to a human.

| Trigger                        | Description                                                                         | Priority |
|--------------------------------|-------------------------------------------------------------------------------------|----------|
| Legal threats                  | Mentions of lawsuits, lawyers, regulatory complaints (GDPR, CCPA, HIPAA)            | CRITICAL |
| Data breach / security incident| Reports of unauthorized access, suspected breach, data loss                         | CRITICAL |
| Refund demand > $500           | Large refund requests require finance team authorization                             | HIGH     |
| Contract disputes              | Any dispute referencing a signed agreement or SLA violation                         | HIGH     |
| Executive escalation           | Customer identifies as C-level or requests to speak to NovaSync leadership          | HIGH     |
| Churn threat (Business/Enterprise) | Paid-tier customers explicitly stating intent to cancel                        | HIGH     |

---

## TIER 2 – Escalate After One Failed AI Attempt

The agent attempts resolution once. If the customer remains unsatisfied, escalate.

| Trigger                        | Description                                                                         | Priority |
|--------------------------------|-------------------------------------------------------------------------------------|----------|
| Pricing negotiation            | Customer asks for discounts, custom pricing, or non-standard terms                  | MEDIUM   |
| Repeated same issue            | Customer has contacted support 3+ times for the same unresolved problem             | MEDIUM   |
| Unresolved technical bug       | Issue cannot be found in knowledge base; appears to be a product-level bug          | MEDIUM   |
| Account compromise             | Customer believes account was accessed by an unauthorized party                     | MEDIUM   |
| Angry or abusive customer      | Sentiment anger score ≥ 0.75 or profanity detected                                  | MEDIUM   |
| Feature commitment request     | Customer wants a guaranteed delivery date for a specific feature                    | MEDIUM   |

---

## TIER 3 – Agent Judgment Escalation

Agent may use judgment based on full conversation context.

| Trigger                        | Description                                                                         | Priority |
|--------------------------------|-------------------------------------------------------------------------------------|----------|
| Complex multi-system issue     | Problem spans 3+ integrations or external services with unclear root cause          | LOW      |
| Ambiguity after 2 clarifications | Customer's issue remains unclear after two follow-up exchanges                    | LOW      |
| High-value account (>$1,000/mo) | Extra care warranted for high-revenue accounts regardless of issue type            | LOW      |
| VIP customer flag              | Customer is flagged as VIP in the CRM system                                        | LOW      |
| Compliance questions           | HIPAA, SOC 2, GDPR questions beyond what standard documentation covers              | LOW      |

---

## Sentiment-Based Escalation Thresholds

| Signal                    | Threshold          | Action                  |
|---------------------------|--------------------|-------------------------|
| Anger score               | ≥ 0.75             | Immediate escalation    |
| Frustration score         | ≥ 0.80 (2+ messages) | Escalate after attempt |
| Profanity detected        | Any instance       | Immediate escalation    |
| Urgency keywords          | "losing money", "right now", "immediately", "shut down" | Flag + expedite |

---

## Escalation Process

When escalation is triggered, the agent must:

1. Acknowledge the customer warmly and set expectations
2. Provide an estimated wait time based on plan SLA
3. Create an escalation ticket containing:
   - Full conversation history
   - Detected issue category
   - Escalation trigger reason
   - Sentiment scores
   - Customer tier and account value
4. Notify the human agent queue via internal alert
5. Send confirmation to customer with ticket reference number

**Standard Escalation Message:**
```
I want to make sure you get the best possible support here. I'm connecting you
with one of our specialized team members who can assist you directly.
You'll hear back within [SLA based on plan]. Your reference number is [TICKET_ID].
```

---

## Anti-Escalation Guidelines

The agent must NOT escalate for:
- Standard password resets
- Invoice retrieval or plan explanation
- Basic how-to questions with documented answers
- Routine bug reports with known fixes
- Feature availability questions

Unnecessary escalation degrades the customer experience and wastes human agent capacity.

---

## Key Escalation Metrics (Stage 1 Targets)

- Overall escalation rate: < 20% of all tickets
- False escalation rate (human resolved in < 2 min): < 5%
- Customer satisfaction post-escalation: ≥ 4.2/5.0
- Average escalation resolution time: < SLA ceiling for plan tier
