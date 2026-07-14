# Vista Hackathon 2026 — Idea Bank

**Event:** July 13–15, 2026 · Scottsdale, AZ
**Team:** Finastra Payments
**Requirement:** Agentic AI orchestration as core component

---

## Idea A — Payment Exception Resolution Agent

**Theme bet:** Operational efficiency, AI in operations

### Problem
Banks and corporates resolve thousands of failed/unmatched payments manually, clicking through 5+ systems per case. Slow, expensive, error-prone.

### Solution
Multi-agent system that autonomously triages and resolves payment exceptions:
1. **Intake agent** — ingests a failed payment event, classifies the error type
2. **Investigation agent** — queries payment records, SWIFT message fields, counterparty directory to diagnose root cause
3. **Resolution agent** — proposes a repair (or executes it): re-submit, cancel, amend field, escalate

### Demo moment
> "Watch it fix a broken SWIFT payment in real time" — agent receives a failed `pacs.008`, calls tools, diagnoses a bad IBAN checksum, proposes the corrected message.

### Mock data needed
| Dataset | Key fields |
|---|---|
| Payment transactions | `tx_id`, `sender_bic`, `receiver_bic`, `sender_iban`, `receiver_iban`, `amount`, `currency`, `status`, `error_code`, `timestamp` |
| Error code catalog | `error_code`, `description`, `standard_remediation` |
| Bank/BIC directory | `bic`, `bank_name`, `country`, `correspondent_banks` |
| Resolution history | Past cases + resolutions (agent memory/context) |

**Pre-craft failure scenarios:** bad IBAN checksum, duplicate tx reference, missing mandatory field, sanctions hit, FX limit breach.

### Why it wins
- Clearest agentic story: perceive → reason → act
- Visceral live demo
- Obvious productization path
- Works regardless of theme announced
- Built-in Responsible AI angle (human-in-the-loop approval before execution)

---

## Idea B — Sanctions / Compliance Triage Orchestrator

**Theme bet:** Risk, compliance, responsible AI

### Problem
Sanctions screening false positive rates are ~95%. Every flagged transaction gets manually reviewed by compliance analysts — slow, expensive, inconsistent.

### Solution
Multi-agent triage pipeline:
1. **Screening agent** — runs transaction against sanctions lists, computes match score
2. **Research agent** — queries OFAC SDN structure, adverse media, entity profiles to disambiguate
3. **Decision agent** — produces structured recommendation (approve / hold / reject) with full reasoning audit trail

### Demo moment
> "Acme Trading Co." flags against a sanctioned "ACME Trade Corp." — agent researches both entities, concludes they're distinct, approves with documented reasoning.

### Mock data needed
| Dataset | Key fields |
|---|---|
| Flagged transactions | Same as Idea A + `screening_hit`, `matched_entity`, `match_score` |
| Sanctions list (simplified OFAC SDN) | `entity_name`, `aliases`, `country`, `list_type`, `date_added` |
| Entity profiles | `name`, `address`, `country`, `entity_type`, `risk_score` |
| Adverse media | Mock news snippets tied to entity names |
| Historical decisions | Prior case + reasoning + outcome |

### Why it wins
- Multi-agent architecture is legible to judges
- Audit trail = built-in Responsible AI story
- Compliance is a perennial fintech pain point
- Near-miss disambiguation scenarios are visually compelling

---

## Idea C — Intelligent Cross-Border Payment Routing Agent

**Theme bet:** Customer experience, cross-border payments

### Problem
Selecting the optimal route for a cross-border payment (FX rate, correspondent fees, settlement time, counterparty risk) is complex — treasury teams do it manually or rely on static rules.

### Solution
Agent that reasons across multiple routing factors for a given payment and recommends the optimal route with a human-readable explanation of tradeoffs.

### Demo moment
> USD → BRL, $500K, "settle within 4 hours" — agent evaluates 3 corridors, recommends one that balances cost and speed, explains why it rejected the alternatives.

### Mock data needed
| Dataset | Key fields |
|---|---|
| FX rates | `pair`, `bid`, `ask`, `timestamp` |
| Corridors | `from_currency`, `to_currency`, `rail`, `avg_settlement_hours`, `fee_structure` |
| Correspondent network | `bank_a → bank_b`, `hop_fee`, `reliability_score` |
| Counterparty risk | `bic`, `country_risk`, `bank_rating` |

### Why it wins
- Side-by-side route comparison is visually clear
- Strong reasoning showcase
- Non-technical teammates can easily explain the value

---

## Idea D — Conversational Payment Operations Interface

**Theme bet:** AI-first UX, developer experience, accessibility

### Problem
Payment operations teams navigate complex legacy UIs with hundreds of fields across dozens of screens to investigate a single stuck payment. Context-switching is constant, tribal knowledge is required.

### Solution
A natural language interface backed by a multi-agent backend. An analyst asks "why did this payment get stuck?" and the orchestration layer fans out to the right specialist agents — transaction lookup, message parsing, counterparty check — then synthesizes a narrative response with recommended next actions.

### Demo moment
> Analyst types: *"Find all EUR payments over €100K that failed in the last 24 hours and tell me why."* Agent investigates, returns a structured summary with root causes and one-click remediation options.

### Mock data needed
| Dataset | Key fields |
|---|---|
| Payment transactions | Same as Idea A |
| Error catalog | `error_code`, `plain_english_explanation`, `suggested_action` |
| Agent tool registry | List of callable tools + descriptions (what the orchestrator can invoke) |

### Why it wins
- Most accessible demo — judges immediately understand the value without payments domain knowledge
- Natural language layer makes the agentic orchestration very legible
- Can be layered on top of Idea A's architecture — doubles as a UI for that agent
- Strong "AI-first product" narrative for productization

---

## Idea E — ISO 20022 Migration & Validation Agent

**Theme bet:** Infrastructure modernization, payments standards

### Problem
Banks are mid-migration from legacy SWIFT MT messages (e.g., MT103) to ISO 20022 XML (e.g., pacs.008). This involves field mapping, data truncation handling, and exception management — largely manual today. SWIFT mandate is active now.

### Solution
Multi-agent pipeline that ingests MT messages, translates to ISO 20022, flags mapping ambiguities, resolves them using configurable business rules, and generates a migration quality report.

1. **Parser agent** — decodes the incoming MT message structure
2. **Mapping agent** — applies field-level translation rules, flags truncations and missing mappings
3. **Validation agent** — checks the output pacs.008 against the ISO 20022 schema, scores completeness
4. **Report agent** — produces a human-readable migration summary with issue counts and remediation steps

### Demo moment
> Feed it a batch of 10 MT103 messages. Agent produces translated pacs.008 outputs, highlights 2 truncation issues, 1 missing remittance field, and explains how each was or wasn't resolved.

### Mock data needed
| Dataset | Key fields |
|---|---|
| MT103 messages | Raw SWIFT message strings (20–30 realistic samples) |
| Mapping rules | `mt_field → iso_field`, `truncation_limit`, `fallback_rule` |
| ISO 20022 schema | Simplified pacs.008 field definitions and cardinality rules |
| Validation results | Expected output per input (for demo script) |

### Why it wins
- Extremely timely — SWIFT's ISO 20022 mandate is live and every bank is dealing with this
- Very Finastra-relevant domain expertise
- Technical architecture is clean and demonstrable
- Strong productization story — every bank needs this

---

## Idea F — Intraday Liquidity Management Agent

**Theme bet:** Treasury, cash management, real-time finance

### Problem
Corporate treasurers manually monitor cash positions across multiple bank accounts, currencies, and entities throughout the day. Decisions about when to sweep, invest overnight, or draw on credit lines are time-sensitive and based on fragmented data.

### Solution
Agent that continuously monitors intraday cash positions, forecasts end-of-day balances using expected payment flows, and proactively recommends (or executes) fund movements.

1. **Monitor agent** — polls account balances and intraday transaction feeds
2. **Forecast agent** — projects end-of-day positions based on pending payments and historical patterns
3. **Action agent** — recommends sweeps, investments, or credit line draws; flags shortfalls before they happen

### Demo moment
> Agent detects that a subsidiary account will be $2.3M short by 4 PM, identifies a surplus in the parent entity's GBP account, proposes a same-day intercompany transfer with FX conversion, and shows the projected post-action position.

### Mock data needed
| Dataset | Key fields |
|---|---|
| Account balances | `account_id`, `entity`, `currency`, `balance`, `timestamp` |
| Pending payments | `tx_id`, `direction`, `amount`, `currency`, `expected_settlement` |
| Intercompany rules | Which entities can transfer to which, limits, FX allowed |
| Credit facilities | `facility_id`, `limit`, `drawn`, `rate`, `availability` |

### Why it wins
- High business value — liquidity shortfalls are costly
- Proactive agent behavior (acts before a problem occurs) is more impressive than reactive
- CFO-level demo appeal — easy for non-technical judges to understand the stakes

---

## Idea G — Fraud Investigation & Triage Agent

**Theme bet:** Fraud, risk, real-time decisioning

### Problem
Fraud analysts review hundreds of flagged transactions daily across multiple systems — transaction history, device data, behavioral patterns, merchant data — to decide block or allow. Manual, slow, and inconsistent under volume.

### Solution
Multi-agent investigation system triggered by a fraud alert:
1. **Context agent** — pulls full transaction history for the sender, recent geolocation, device fingerprint
2. **Pattern agent** — compares against known fraud patterns and historical false positives
3. **Decision agent** — recommends block / allow / step-up authentication with a risk score and plain-English rationale

### Demo moment
> A card-not-present transaction fires a fraud alert. Agent investigates: this customer transacted in London 2 hours ago, now appears in Lagos, amount is 3x their average. Recommends block with explanation. Contrast with a false positive it correctly clears.

### Mock data needed
| Dataset | Key fields |
|---|---|
| Transaction history | `customer_id`, `merchant`, `amount`, `currency`, `location`, `device_id`, `timestamp` |
| Fraud patterns | `pattern_id`, `description`, `rule`, `historical_fp_rate` |
| Customer profiles | `customer_id`, `home_country`, `avg_tx_amount`, `typical_merchants` |
| Alert queue | `alert_id`, `tx_id`, `alert_reason`, `score`, `status` |

### Why it wins
- Emotionally resonant demo — everyone understands fraud
- Clear before/after: analyst time drops from 15 min to 30 seconds per case
- Responsible AI angle is natural: explainability, bias in fraud scoring
- False positive correction scenario differentiates from simple rules-based systems

---

## Idea H — Real-Time Payment Exception & Recall Agent

**Theme bet:** Real-time payments, operational resilience
**Finastra fit:** Global PAYplus, Payment To (FedNow/RTP/SEPA Instant)

### Problem
Real-time payment rails (FedNow, RTP, SEPA Instant) are irrevocable — you cannot simply cancel and resubmit a failed or misdirected payment. Instead, banks must navigate formal recall, Request for Information (RfI), and return workflows, each with strict scheme-mandated timelines. Most banks handle this manually today and routinely miss SLA windows.

### Solution
Agent that manages the full post-payment exception lifecycle on real-time rails:
1. **Detection agent** — identifies misdirected, duplicate, or disputed real-time payments
2. **Workflow agent** — determines the correct scheme workflow (recall, RfI, return) and initiates it within the SLA window
3. **Negotiation agent** — manages counterparty responses, escalates stalled cases, tracks resolution status
4. **Reporting agent** — maintains an audit trail and SLA compliance dashboard

### Demo moment
> A FedNow payment lands in the wrong account. Agent detects it, identifies the correct recall workflow, sends the recall request to the receiving bank within 10 minutes, and tracks the response — all without human intervention.

### Mock data needed
| Dataset | Key fields |
|---|---|
| Real-time payment events | `tx_id`, `rail` (FedNow/RTP), `sender`, `receiver`, `amount`, `status`, `timestamp` |
| Exception queue | `exception_type` (misdirected/duplicate/disputed), `detected_at`, `sla_deadline` |
| Scheme workflow rules | `exception_type → workflow`, `max_response_hours`, `escalation_path` |
| Counterparty responses | `recall_id`, `status`, `response_time`, `resolution` |

### Why it wins
- Extremely timely — FedNow volume is exploding and real-time exception handling is an unsolved problem at most banks
- Irrevocability makes the stakes visceral and immediate
- Direct fit for Global PAYplus + Payment To product lines
- SLA countdown in the demo creates urgency judges will feel

---

## Idea I — Nostro/Vostro Reconciliation Agent

**Theme bet:** Operational efficiency, correspondent banking
**Finastra fit:** Global PAYplus (core banking operations workflow)

### Problem
Banks running correspondent payment flows must reconcile their nostro accounts daily — matching debits and credits on SWIFT MT940/camt.053 statements against expected payment flows. Breaks (unmatched items) require manual investigation across multiple systems. A mid-size bank can have hundreds of breaks per day.

### Solution
Multi-agent reconciliation pipeline:
1. **Ingest agent** — parses incoming nostro statements (MT940 or camt.053 format), normalises fields
2. **Matching agent** — runs fuzzy matching against expected payment flows, handles amount/date tolerances
3. **Investigation agent** — for unmatched items, queries payment records and correspondent bank data to diagnose the break
4. **Resolution agent** — recommends action: claim from correspondent, internal journal entry, or escalate to ops team

### Demo moment
> 50 nostro statement entries, 47 auto-matched. Agent investigates the 3 breaks: one is a value date mismatch (auto-resolved), one is a duplicate credit from a correspondent (claim initiated), one requires human review (escalated with full context pre-populated).

### Mock data needed
| Dataset | Key fields |
|---|---|
| Nostro statements | `statement_id`, `account`, `currency`, `entries[]` with `amount`, `value_date`, `reference`, `narrative` |
| Expected payment flows | `tx_id`, `amount`, `currency`, `value_date`, `correspondent_bic`, `our_reference` |
| Matching tolerances | `field`, `tolerance_type`, `tolerance_value` |
| Correspondent bank directory | `bic`, `bank_name`, `typical_value_date_lag` |

### Why it wins
- Daily pain point at every bank running correspondent payments — enormous scale of the problem
- Quantifiable ROI: break resolution time from hours to minutes
- camt.053 / MT940 are real formats judges from banks will recognise
- Natural human-in-the-loop story for the unresolvable cases

---

## Idea J — SWIFT gpi Proactive Tracking & Escalation Agent

**Theme bet:** Customer experience, correspondent banking transparency
**Finastra fit:** Global PAYplus (SWIFT-connected customer base)

### Problem
SWIFT gpi provides end-to-end payment tracking, but banks still manually chase payments that are delayed or stuck at a correspondent. Relationship managers spend hours per week sending gpi status queries. End customers call asking where their money is.

### Solution
Agent that monitors gpi tracking data and acts before customers ask:
1. **Monitor agent** — watches gpi tracker for all in-flight payments, flags any approaching SLA breach
2. **Diagnosis agent** — identifies where in the chain a payment is stuck and why (cut-off time, compliance hold, liquidity issue)
3. **Escalation agent** — autonomously sends gpi payment status queries to the stuck correspondent, logs responses
4. **Notification agent** — proactively updates the originating bank and optionally the end customer with plain-English status

### Demo moment
> A USD cross-border payment to Singapore has been sitting at an intermediary for 6 hours. Agent detects the SLA risk, queries the correspondent, gets back a "compliance hold" response, notifies the ops team with context and suggested next steps — before anyone picked up the phone.

### Mock data needed
| Dataset | Key fields |
|---|---|
| gpi tracker feed | `uetr`, `payment_status`, `current_agent_bic`, `last_update`, `sla_deadline` |
| Correspondent profiles | `bic`, `typical_processing_time`, `cut_off_times`, `known_hold_reasons` |
| SLA rules | `corridor`, `rail`, `max_hours_per_agent`, `total_sla_hours` |
| Status query templates | Pre-built gpi camt.057 message structures |

### Why it wins
- Proactive agent behaviour (acts before the problem escalates) is the most impressive agentic pattern
- gpi is a live SWIFT standard — every Global PAYplus bank is on it
- Customer experience story is easy for non-technical judges to grasp
- Responsible AI angle: agent sends messages on behalf of the bank — clear human approval workflow needed

---

## Idea K — Payment Rail Onboarding & Configuration Agent

**Theme bet:** Platform / developer experience, payments modernisation
**Finastra fit:** Global PAYplus professional services acceleration

### Problem
When a bank wants to add a new payment rail to Global PAYplus (e.g., onboard to FedNow, add SEPA Instant), Finastra's professional services team manually configures routing rules, scheme parameters, cut-off times, liquidity limits, and exception workflows. This takes weeks and is highly error-prone.

### Solution
Agent that accelerates rail onboarding by generating, validating, and testing configuration:
1. **Requirements agent** — takes a bank's onboarding questionnaire (rail, volumes, corridors, cut-offs) as input
2. **Configuration agent** — generates the Global PAYplus configuration artefacts (routing rules, scheme parameters, limits)
3. **Validation agent** — checks the configuration against scheme operating rules, flags violations
4. **Test agent** — runs a suite of synthetic test payments through the configuration, validates responses against expected outcomes

### Demo moment
> Input: "Onboard First Community Bank to FedNow — max transaction $500K, 7am–10pm ET operating window, positive pay only." Agent generates the full configuration, validates it against FedNow operating rules, runs 10 synthetic test payments, and produces a readiness report in 3 minutes.

### Mock data needed
| Dataset | Key fields |
|---|---|
| Onboarding questionnaire schema | `bank_id`, `rail`, `max_tx_amount`, `operating_hours`, `corridors`, `liquidity_limits` |
| Scheme operating rules | `rail`, `rule_id`, `description`, `constraint`, `error_if_violated` |
| Configuration templates | Baseline Global PAYplus config structures per rail |
| Test payment scenarios | `scenario_id`, `input_payment`, `expected_outcome` |

### Why it wins
- Directly productisable into Finastra's professional services workflow — obvious path to GA feature
- Reduces onboarding from weeks to hours — massive ROI narrative
- Technical architecture (configuration generation + validation + testing) showcases multiple agent types
- Judges from Finastra will immediately recognise the pain point

---

## Preparation Checklist (pre-July 13)

> Per FAQ: no pre-building of application logic. Environment setup is allowed.

- [ ] Create AWS account, add all 5 teammates as IAM users
- [x] Request Bedrock model access (Claude Sonnet) — can take time, do early
- [ ] Create GitHub org/repo, add all teammates (judges review commit history)
- [x] Install Claude Code / Cursor on laptop, configure against repo
- [ ] Set up basic CI/CD skeleton (GitHub Actions → AWS deploy)
- [ ] Pre-generate mock data JSON files (allowed — not application logic)
- [ ] Sketch MCP server tools needed for chosen idea
- [ ] Decide on AI framework (recommendation: Claude + MCP via AWS Bedrock)

---

## Theme → Idea Decision Map (use at 8 AM when theme drops)

Spend max 15 minutes deciding. Don't debate — pick and commit.

| If the theme is about... | Lead with |
|---|---|
| Operational efficiency / automation | A or I |
| Real-time payments / modernisation | H or K |
| Customer experience / transparency | D or J |
| Risk / compliance / responsible AI | B or G |
| Cross-border / financial inclusion | C or J |
| Open-ended / "build anything agentic" | K or A |

---

## Notes

- **Mock data is the right call** — real payments data has PII/compliance issues. 20–50 records per dataset is enough. Judges care about agent reasoning quality, not data volume.
- **Judges review commit history** — everyone on the team needs to be committing throughout the event, not just at the end.
- **Responsible AI Assessment is required** — each idea has a natural angle (human-in-the-loop, audit trails, bias/false positive reduction).
- **Theme announced at hackathon start (July 14, 8 AM)** — use the decision map above, don't deliberate.
- **Finastra PM on team** — lean on him to validate which idea matches real customer pain and to own the problem statement / slide deck.
