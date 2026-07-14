# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**PayInvestigator** — AI-powered multi-agent system that autonomously investigates and triages payment exceptions. Built for the Vista Hackathon 2026 (July 13–15, Scottsdale AZ). Submission deadline: July 15, 8:00 AM.

The core value prop: replace 15–45 minutes of manual analyst work (clicking through 5+ systems) with a structured, auditable AI investigation in seconds. Target integration: Finastra Global PAYplus.

## Tech Stack

| Layer | Choice |
|---|---|
| AI / LLM | Claude `claude-sonnet-4-6` via Anthropic API or AWS Bedrock |
| Agent framework | Python + `anthropic` SDK tool use (no heavy framework) |
| Backend | FastAPI (Python) |
| Data store | JSON files + SQLite (no infra overhead) |
| Frontend | React or plain HTML/JS |
| Infra | Terraform (AWS) — localhost is acceptable for live demo |

## Agent Architecture

```
Exception Event
      │
      ▼
┌─────────────────┐
│  Intake Agent   │  ← Classifies exception type, extracts key fields
└────────┬────────┘
         ▼
┌─────────────────┐
│ Investigation   │  ← Pulls payment record, SWIFT message, error code
│    Agent        │    Queries counterparty directory, account status
└────────┬────────┘
    ┌────┴────┐
    ▼         ▼
┌───────┐  ┌──────────┐
│Compli-│  │Technical │  ← Parallel sub-agents based on exception type
│ance   │  │Diagnosis │
│Agent  │  │Agent     │
└───┬───┘  └────┬─────┘
    └─────┬─────┘
          ▼
┌─────────────────┐
│ Resolution      │  ← Synthesizes findings, recommends action
│ Agent           │    REQUIRES human approval before any execution
└─────────────────┘
```

**Human-in-the-loop is non-negotiable**: the Resolution Agent recommends only — no payment action executes without explicit human approval. This is a judging criterion and a Responsible AI requirement.

## Repo Structure

```
backend/    # FastAPI app + agent logic
frontend/   # React or HTML/JS investigation UI
infra/      # Terraform (AWS)
docs/       # Implementation plan, idea bank, FAQ
```

## Demo Scenarios (must work for submission)

Three pre-crafted scenarios the live demo must nail:

1. **Bad IBAN checksum** — Technical Diagnosis → agent corrects and re-proposes in ~10 seconds
2. **Sanctions screening hit** — sender name partial-matches SDN list → Compliance Agent researches, recommends hold + rationale
3. **Duplicate payment** — same payment submitted twice → agent detects, recommends cancel on the second

## Mock Data Sets

All data lives as JSON files (no real PII). Generate ~30 records each:

- `payment_transactions` — `tx_id`, `sender_bic`, `receiver_bic`, `sender_iban`, `receiver_iban`, `amount`, `currency`, `status`, `error_code`, `timestamp`
- `error_code_catalog` — `error_code`, `description`, `plain_english_explanation`, `standard_remediation`
- `bic_directory` — `bic`, `bank_name`, `country`, `correspondent_banks[]`
- `sanctions_list` — `entity_name`, `aliases[]`, `country`, `list_type` (simplified OFAC SDN)
- `resolution_history` — past cases + resolutions (agent context/memory)

## Backend Commands

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload          # dev server on :8000
pytest                             # run all tests
pytest tests/test_agents.py -k "intake"  # run single test
```

## Frontend Commands

```bash
cd frontend
npm install
npm run dev       # dev server
npm run build     # production build
```

## Infra Commands

```bash
cd infra
terraform init
terraform plan
terraform apply   # confirm with user before running
```

## Key Constraints

- **Every team member must commit throughout the event** — Vista runs an automated agent to assess commit distribution and timestamps. Don't batch commits at the end.
- **No pre-built application logic** — environment setup only was allowed before July 14, 8 AM start.
- **Responsible AI Assessment required for submission** — audit trail, human approval gate, explainability, and false-positive/escalation handling must be demonstrable.
- **Agentic AI orchestration must be the core** — parallel specialist agents coordinated by an orchestration layer is the architectural requirement.

## Agent Tool Calls (function calling pattern)

Agents call mock tools to retrieve data — not external APIs. Tools to implement:
- `get_payment_record(tx_id)` → transaction details
- `get_swift_message(tx_id)` → raw SWIFT/pacs.008 message
- `get_error_description(error_code)` → error catalog entry
- `check_sanctions(entity_name)` → sanctions list match + score
- `get_bic_info(bic)` → bank/counterparty details
- `get_resolution_history(error_code)` → similar past cases

## Judging Criteria

Judges evaluate: completeness of the challenge prompt, quality of live demo, feasibility of productization, and technical architecture. Judges include Vista MDs/SVPs — pitch at executive level.
