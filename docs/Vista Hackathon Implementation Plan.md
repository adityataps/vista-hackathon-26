# Vista Hackathon — Implementation Plan
**Theme:** Build a product Finastra would want to buy
**Decision:** Payment Exception Investigation by AI Agents

---

## Product Concept

**PayInvestigator** — an AI-powered multi-agent system that autonomously investigates and triages payment exceptions, replacing hours of manual analyst work with a structured, auditable resolution in seconds.

### Problem Statement
When a payment fails or gets flagged, ops teams manually click through 5+ systems to investigate — SWIFT messages, transaction records, counterparty directories, sanctions lists, error catalogs. A mid-size bank resolves hundreds of exceptions per day. Each case takes 15–45 minutes manually.

### Why Finastra Would Buy This
- Slots directly into **Global PAYplus** as an AI investigation layer
- Reduces exception resolution time from hours → seconds
- Full audit trail satisfies regulatory requirements
- Human-in-the-loop approval before any action is taken

### Security/Compliance Angle (baked in, not a separate product)
Compliance holds (sanctions hits, AML flags) are one of the exception types the system handles — the compliance research agent queries screening results, adverse media, and entity profiles as part of its investigation. This covers the security compliance theme without splitting the product.

---

## Agent Architecture

```
Exception Event
      │
      ▼
┌─────────────────┐
│  Intake Agent   │  ← Classifies exception type, extracts key fields
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Investigation   │  ← Pulls payment record, SWIFT message, error code
│    Agent        │    Queries counterparty directory, account status
└────────┬────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌───────┐  ┌──────────────┐
│Compli-│  │  Technical   │  ← Parallel sub-agents based on exception type
│ance   │  │  Diagnosis   │
│Agent  │  │  Agent       │
└───┬───┘  └──────┬───────┘
    └──────┬───────┘
           │
           ▼
┌─────────────────┐
│ Resolution      │  ← Synthesizes findings, recommends action
│ Agent           │    Requires human approval before execution
└─────────────────┘
```

**Exception types to handle (demo scenarios):**
1. Bad IBAN checksum → Technical Diagnosis → auto-correctable
2. Duplicate payment reference → Technical Diagnosis → recommend cancel
3. Sanctions screening hit → Compliance Agent → recommend hold + escalate
4. Missing mandatory ISO 20022 field → Technical Diagnosis → field repair suggestion
5. FX limit breach → Technical Diagnosis + Compliance → recommend review

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

### Datasets needed
- **Payment transactions** — `tx_id`, `sender_bic`, `receiver_bic`, `sender_iban`, `receiver_iban`, `amount`, `currency`, `status`, `error_code`, `timestamp`
- **Error code catalog** — `error_code`, `description`, `plain_english_explanation`, `standard_remediation`
- **Bank/BIC directory** — `bic`, `bank_name`, `country`, `correspondent_banks[]`
- **Sanctions list (simplified OFAC SDN)** — `entity_name`, `aliases[]`, `country`, `list_type`
- **Resolution history** — past cases + what fixed them (gives agent memory context)

### Pre-crafted demo scenarios (script these exactly)
1. **The easy win** — bad IBAN checksum, agent corrects and re-proposes in 10 seconds
2. **The compliance hold** — sender name partial-matches SDN list, agent researches, recommends hold + provides rationale
3. **The duplicate** — same payment submitted twice, agent detects and recommends cancel on the second

---

## 24-Hour Build Timeline

| Window | Goal |
|---|---|
| **Hour 0–1** | Finalize architecture, generate all mock data, scaffold repo |
| **Hour 1–4** | Intake Agent + Investigation Agent working end-to-end |
| **Hour 4–8** | Compliance Agent + Technical Diagnosis Agent |
| **Hour 8–12** | Resolution Agent + orchestration layer stitching all agents |
| **Hour 12–16** | FastAPI endpoints, frontend wired up, demo scenario 1 working |
| **Hour 16–20** | Demo scenarios 2 + 3, polish agent outputs to be readable |
| **Hour 20–22** | Full dry-run of demo, fix any rough edges |
| **Hour 22–24** | Slides, Responsible AI Assessment, submission |

---

## Demo Script (live presentation)

1. **Slide 1** — Team name + members
2. **Slide 2** — Problem: show a screenshot of a "manual investigation" — 5 tabs open, 45 minutes per case
3. **Live demo:**
   - Trigger exception scenario 1 (IBAN error) — watch agent investigate and resolve
   - Trigger exception scenario 2 (sanctions hit) — watch compliance agent flag and explain
4. **Business value** — cost per exception manually vs. with PayInvestigator, volume at scale
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
