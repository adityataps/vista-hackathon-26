# Vista Hackathon — Implementation Plan
**Theme:** Build a product Finastra would want to buy
**Decision:** Payment Exception Investigation by AI Agents

---

## Product Concept

**PayInvestigator** — an AI-powered multi-agent system with two modes: it autonomously investigates and triages payment exceptions (reactive), and continuously monitors in-flight payments to detect and surface bottlenecks before they become failures (proactive).

### Problem Statement
Payment ops teams are always fighting on two fronts:
1. **Exceptions** — when a payment fails, analysts manually click through 5+ systems to investigate. Each case takes 15–45 minutes. A mid-size bank handles hundreds per day. + Costs
2. **Bottlenecks** — slow in-flight payments sit undetected until a customer calls. By then, the SLA window has closed and the damage is done.

Both problems share the same root cause: no system connects the dots across payment lifecycle events, correspondent data, and business rules automatically.

### Why Finastra Would Buy This
- Slots directly into **Global PAYplus** as an AI investigation + monitoring layer
- Reactive mode: exception resolution time from 45 min → seconds
- Proactive mode: catches bottlenecks before SLA breach, before the customer calls
- Full audit trail satisfies regulatory requirements
- Human-in-the-loop approval before any action is taken

### Security/Compliance Angle (baked in, not a separate product)
Compliance holds (sanctions hits, AML flags) are one of the exception types the system handles — the compliance research agent queries screening results, adverse media, and entity profiles as part of its investigation. This covers the security compliance theme without splitting the product.

---

## Agent Architecture

Two tracks, shared resolution layer.

```
TRACK 1 — REACTIVE (Exception Resolution)
═══════════════════════════════════════════════════════
Failed Payment Event
      │
      ▼
┌─────────────────┐
│  Intake Agent   │  ← Classifies exception type, extracts key fields
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Investigation   │  ← Pulls payment record, SWIFT message, error code,
│    Agent        │    counterparty directory, account status
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌──────────┐  ┌──────────────┐
│Compliance│  │  Technical   │  ← Parallel sub-agents based on exception type
│  Agent   │  │  Diagnosis   │
└────┬─────┘  └──────┬───────┘
     └────────┬───────┘
              │
              ▼
      ┌───────────────┐
      │  Resolution   │  ← Synthesizes findings, recommends action (HITL gate)
      │    Agent      │
      └───────────────┘


TRACK 2 — PROACTIVE (Bottleneck Detection)
═══════════════════════════════════════════════════════
Payment Lifecycle Event Stream (continuous)
      │
      ▼
┌─────────────────┐
│  Monitor Agent  │  ← Watches all in-flight payments, compares elapsed
│                 │    time per step against SLA benchmarks
└────────┬────────┘
         │  (SLA risk detected)
         ▼
┌──────────────────────┐
│ Bottleneck Analysis  │  ← Identifies WHERE the delay is occurring:
│       Agent          │    which step, which correspondent, which corridor
└────────┬─────────────┘
         │
         ▼
┌─────────────────┐
│  Pattern Agent  │  ← Checks if this is systemic: are multiple payments
│                 │    through the same correspondent delayed? Same rail?
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Alert Agent   │  ← Notifies ops team with context pre-populated:
│                 │    which payments at risk, root cause hypothesis,
│                 │    recommended escalation action
└─────────────────┘
```

**Exception types handled (Track 1):**
1. Bad IBAN checksum → Technical Diagnosis → auto-correctable
2. Duplicate payment reference → Technical Diagnosis → recommend cancel
3. Sanctions screening hit → Compliance Agent → recommend hold + escalate
4. Missing mandatory ISO 20022 field → Technical Diagnosis → field repair suggestion
5. FX limit breach → Technical Diagnosis + Compliance → recommend review

**Bottleneck patterns detected (Track 2):**
1. Single payment stuck at correspondent beyond SLA threshold
2. Systemic delay — multiple payments delayed through same intermediary
3. Rail degradation — a payment rail (e.g., SEPA Instant) showing elevated processing times
4. Cut-off risk — payment approaching correspondent cut-off with no confirmation yet

---

## Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| AI / LLM | Claude claude-sonnet-4-6 (Anthropic API direct or Bedrock) | Best tool use + reasoning |
| Agent framework | Python + `anthropic` SDK tool use (no heavy framework) | Fastest to build and debug in 24h |
| Tool connectivity | MCP or direct function calls | MCP if time allows, otherwise native tool use |
| Backend | FastAPI (Python) | Fast to stand up, easy to demo |
| Mock data store | JSON files + in-memory / SQLite | No infra overhead |
| Frontend | Simple React or plain HTML/JS | PM/UX can own this |
| Infra | AWS (EC2 or Lambda) or just localhost for demo | Localhost is fine for live demo |
| Repo | GitHub | Judges review commit history |

---

## Team Swim Lanes

| Role | Owner | Responsibilities |
|---|---|---|
| Backend / AI / Infra | Aditya | Agent logic, orchestration, FastAPI, deployment |
| Product / Demo Script | PM (Finastra veteran) | Exception scenario narrative, slide deck, demo flow |
| Frontend | TBD teammate | Chat/investigation UI, exception queue view |
| Mock Data | Any | Generate realistic payment JSON, SWIFT message samples |
| Responsible AI Assessment | PM + Aditya | Human-in-the-loop design, audit trail, bias considerations |

---

## Mock Data Plan

> Pre-generate before writing any agent code. ~30 records per dataset.

### Track 1 datasets (Exception Resolution)
- **Payment transactions** — `tx_id`, `sender_bic`, `receiver_bic`, `sender_iban`, `receiver_iban`, `amount`, `currency`, `status`, `error_code`, `timestamp`
- **Error code catalog** — `error_code`, `description`, `plain_english_explanation`, `standard_remediation`
- **Bank/BIC directory** — `bic`, `bank_name`, `country`, `correspondent_banks[]`
- **Sanctions list (simplified OFAC SDN)** — `entity_name`, `aliases[]`, `country`, `list_type`
- **Resolution history** — past cases + what fixed them (agent memory context)

### Track 2 datasets (Bottleneck Detection)
- **Payment lifecycle events** — `tx_id`, `step` (submitted / validated / sent_to_correspondent / processing / settled), `step_timestamp`, `expected_duration_minutes`, `actual_duration_minutes`
- **SLA benchmarks** — `corridor`, `rail`, `step`, `p50_minutes`, `p95_minutes`, `breach_threshold_minutes`
- **Correspondent processing stats** — `bic`, `bank_name`, `avg_processing_time_minutes`, `current_status` (normal / degraded / outage)
- **In-flight payment queue** — `tx_id`, `current_step`, `elapsed_minutes`, `sla_deadline`, `risk_level` (on-track / at-risk / breached)

### Pre-crafted demo scenarios (script these exactly)
1. **The easy win** — bad IBAN checksum, agent corrects and re-proposes in 10 seconds (Track 1)
2. **The compliance hold** — sender name partial-matches SDN list, agent researches, recommends hold + rationale (Track 1)
3. **The stuck payment** — USD→SGD payment at Deutsche Bank intermediary for 6h (expected 2h). Monitor agent detects it, Bottleneck Analysis identifies the FX conversion step, Pattern agent finds 3 other payments through the same correspondent also delayed → systemic flag raised (Track 2)
4. **The near-miss** — payment approaching correspondent cut-off in 20 minutes with no processing confirmation. Alert agent fires before SLA breach (Track 2)

---

## 24-Hour Build Timeline

| Window | Goal |
|---|---|
| **Hour 0–1** | Finalize architecture, generate all mock data (both tracks), scaffold repo |
| **Hour 1–4** | Track 1: Intake Agent + Investigation Agent end-to-end |
| **Hour 4–7** | Track 1: Compliance Agent + Technical Diagnosis Agent + Resolution Agent |
| **Hour 7–10** | Track 2: Monitor Agent + Bottleneck Analysis Agent |
| **Hour 10–13** | Track 2: Pattern Agent + Alert Agent, wire both tracks together |
| **Hour 13–17** | FastAPI endpoints, frontend wired up, demo scenarios 1 + 2 working |
| **Hour 17–20** | Demo scenarios 3 + 4 (bottleneck track), polish all agent outputs |
| **Hour 20–22** | Full dry-run of all 4 scenarios, fix rough edges |
| **Hour 22–24** | Slides, Responsible AI Assessment, submission |

---

## Demo Script (live presentation)

1. **Slide 1** — Team name + members
2. **Slide 2** — Problem: show a screenshot of a "manual investigation" — 5 tabs open, 45 minutes per case
3. **Live demo:**
   - Trigger scenario 1 (IBAN error) — exception resolved in seconds
   - Trigger scenario 2 (sanctions hit) — compliance agent flags with reasoning
   - Trigger scenario 3 (stuck payment) — bottleneck detected at correspondent, systemic pattern identified
   - Trigger scenario 4 (cut-off risk) — proactive alert fires before SLA breach
4. **Business value** — two metrics: exception resolution time (45 min → seconds) + bottleneck detection (caught proactively vs. after customer complaint)
5. **Architecture slide** — the agent diagram
6. **Responsible AI Assessment** — human approval gate, full audit trail, no autonomous execution

---

## Responsible AI Assessment (required for submission)

- **Human-in-the-loop:** No payment action is executed without explicit human approval. Agent recommends only.
- **Explainability:** Every recommendation includes a plain-English rationale and the tools/data sources consulted.
- **Audit trail:** Full log of agent reasoning steps, tool calls, and data accessed — satisfies regulatory requirements.
- **Bias / false positives:** Compliance agent is designed to flag uncertainty and escalate rather than auto-reject. Reduces, not replaces, human judgment.
- **Data privacy:** No real PII in demo. In production, would operate within bank's existing data governance perimeter.

---

## Concepts + Technology Reference

- **Multi-agent orchestration** — parallel specialist agents (compliance, technical) coordinated by a resolution agent
- **Tool use / function calling** — agents call mock APIs to retrieve payment records, error codes, sanctions data
- **MCP (Model Context Protocol)** — standard interface for agent-to-tool communication
- **ISO 20022 / pacs.008** — payment message standard (MT103 → ISO 20022 migration context)
- **SWIFT gpi / UETR** — unique end-to-end transaction reference for tracking
- **Human-in-the-loop (HITL)** — approval gate before any resolution action is taken
