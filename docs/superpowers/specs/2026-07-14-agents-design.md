# PayInvestigator — Agent System Design (Track 1)

**Date:** 2026-07-14  
**Scope:** Track 1 — Exception Investigation (reactive mode only)  
**Stack:** LangGraph + AWS Bedrock (`claude-sonnet-4-6`) + FastAPI SSE  

---

## Problem

Faulty pacs.008 payments land in PostgreSQL via the Lambda ingest pipeline. Currently nothing happens next. This design covers the full path from detection → investigation → human decision.

---

## Flow

```
Lambda ingests faulty payment
        │
        ▼
POST /api/ingest/exceptions          ← Lambda calls this
        │  creates exceptions row (status: pending)
        ▼
GET /api/exceptions                  ← Frontend polls / renders queue
        │  analyst clicks Investigate
        ▼
POST /api/exceptions/{msg_id}/investigate
        │  creates investigations row, spawns LangGraph graph as background task
        ▼
GET /api/investigations/{investigation_id}/stream   ← SSE
        │  streams {agent, cls, text} events as graph runs
        ▼
HITL gate — approve / reject
POST /api/resolutions/{report_id}/approve|reject
```

---

## Data Model

### `exceptions` table
Created when Lambda POSTs a faulty payment. One row per faulty payment.

```sql
CREATE TABLE IF NOT EXISTS exceptions (
    id               SERIAL PRIMARY KEY,
    payment_id       INTEGER REFERENCES payments(id),
    msg_id           TEXT UNIQUE NOT NULL,
    uetr             TEXT NOT NULL,
    detected_errors  JSONB NOT NULL,   -- [{code, field, value}]
    status           TEXT NOT NULL DEFAULT 'pending',
                                       -- pending | investigating | awaiting_approval
                                       --   | resolved | escalated
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);
```

`detected_errors` comes from the generator manifest (error codes already classified). The Lambda sends this payload directly.

### `investigations` table
Created when a user triggers an investigation. One row per investigation run.

```sql
CREATE TABLE IF NOT EXISTS investigations (
    id               SERIAL PRIMARY KEY,
    exception_id     INTEGER REFERENCES exceptions(id),
    msg_id           TEXT NOT NULL,
    steps            JSONB NOT NULL DEFAULT '[]',   -- append-only [{agent,cls,text,ts}]
    findings         JSONB,                          -- {technical: {...}, compliance: {...}}
    recommendation   JSONB,                          -- {action, rationale, confidence}
    approval_status  TEXT DEFAULT 'pending',         -- pending | approved | rejected
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    completed_at     TIMESTAMPTZ
);
```

`steps` is written incrementally as the graph runs so the frontend can replay from DB on reconnect.

### Schema management
Both tables created via `CREATE TABLE IF NOT EXISTS` in a `_ensure_schema()` function called at FastAPI startup. No migration tooling — drop and recreate if schema changes during the hackathon.

---

## LangGraph Graph

### State

```python
class InvestigationState(TypedDict):
    payment: dict                # full row from payments table
    detected_errors: list        # [{code, field, value}]
    swift_message: str           # raw XML from payments.raw_xml
    intake_classification: dict  # {error_categories, needs_technical, needs_compliance}
    investigation_context: dict  # assembled context (bic info, iban details, etc.)
    technical_findings: dict     # None until technical node runs
    compliance_findings: dict    # None until compliance node runs
    recommendation: dict         # populated by resolution node
    steps: list                  # append-only stream log
```

### Nodes

```
[intake] → [investigate] → [dispatch] → [technical]  ─┐
                                       → [compliance] ─┴→ [resolution]
```

| Node | Responsibility |
|---|---|
| `intake` | Classifies error categories from `detected_errors`; sets `needs_technical` / `needs_compliance` flags |
| `investigate` | Pulls full payment record + raw XML; assembles `investigation_context` |
| `dispatch` | Uses LangGraph `Send` API to fan out to whichever specialists are needed |
| `technical` | IBAN/BIC/FX/duplicate validation; wraps existing `iban_validator.py` |
| `compliance` | Beneficiary name/address completeness (FATF Travel Rule); sanctions fuzzy match |
| `resolution` | Waits for all specialist results; synthesises recommendation + rationale |

### Dispatch routing

| Error category | Specialist(s) |
|---|---|
| `account_identifier` | technical |
| `routing` | technical |
| `duplicate` | technical |
| `fx` | technical |
| `beneficiary_data` | compliance |
| mixed or sanctions-relevant name | both |

### Tools

| Tool | Node(s) | Implementation |
|---|---|---|
| `get_payment_record(msg_id)` | investigate | DB query on `payments` |
| `validate_iban(iban)` | technical | wraps `pacs008_generator.iban_validator.validate_iban` |
| `validate_bic(bic)` | technical | ISO 3166 country code check on positions 5–6 |
| `check_duplicate(uetr, msg_id)` | technical | DB query on `payments` for matching UETR |
| `check_fx_consistency(instd_amt, sttlm_amt, rate)` | technical | arithmetic check, >1% tolerance = flag |
| `screen_entity(name)` | compliance | fuzzy match against hardcoded SDN list (sanctions data) |
| `check_address_completeness(address)` | compliance | heuristic: requires country + town + street |
| `get_resolution_history(error_code)` | resolution | query `investigations` for prior resolved cases |

---

## FastAPI Endpoints

### Lambda → backend

```
POST /api/ingest/exceptions
Body:  {msg_id, uetr, detected_errors: [{code, field, value}], payment_id?}
Creates exceptions row (status: pending).
Returns: {exception_id}
```

### Frontend — exception queue

```
GET /api/exceptions
Returns: [{tx_id, type, type_key, amount, sender, receiver, status, created_at}]
Shape matches existing mock.exceptionQueue in client.js.
```

### Frontend — trigger investigation + SSE stream

```
POST /api/exceptions/{msg_id}/investigate
Content-Type: text/event-stream  (response is SSE — client reads body as stream)

Creates investigations row, runs LangGraph graph inline, streams events as they happen.

Event shape (stream lines):
  data: {"agent": "Intake Agent", "cls": "intake", "text": "..."}
  data: {"agent": "tool", "cls": "tool", "text": "🔧 validate_iban(iban='DE89...')"}

Final event:
  data: {"type": "done", "report_id": "RPT-...", "recommendation": {"action": "...", "rationale": "..."}}
```

`cls` values: `intake` | `investigate` | `technical` | `compliance` | `resolution` | `tool`

The `investigation_id` is embedded in `report_id` on the `done` event. Steps are also written to `investigations.steps` incrementally so the frontend can replay from DB on reconnect then continue live.

### HITL gate

```
POST /api/resolutions/{report_id}/approve
POST /api/resolutions/{report_id}/reject
Updates investigations.approval_status; logs decision to audit trail.
```

---

## SSE Normalisation

LangGraph `.astream_events(version="v2")` emits raw events. These are normalised to `{agent, cls, text}` before writing to the SSE response:

| LangGraph event | SSE output |
|---|---|
| `on_chat_model_stream` | Buffer tokens; emit complete thoughts as `{agent, cls, text}` |
| `on_tool_start` | `{agent: "tool", cls: "tool", text: "🔧 {tool_name}({args})"}` |
| `on_tool_end` | `{agent: "tool", cls: "tool", text: "↳ {result_summary}"}` |
| graph complete | `{type: "done", report_id, recommendation}` |

No frontend changes needed — `client.js` already handles this exact shape.

---

## Lambda Change

One addition to `jobs/payment-ingest/handler.py`: after a successful `_ingest_record()`, if `is_faulty` is true, POST to `{BACKEND_URL}/api/ingest/exceptions` with the msg_id, uetr, and detected_errors.

`BACKEND_URL` is injected as a Lambda environment variable. The POST is fire-and-forget (non-fatal on failure) — ingest never fails because the backend is unreachable.

---

## File Structure (new files)

```
backend/
├── main.py                    # existing — add new routers + _ensure_schema()
├── agents/
│   ├── __init__.py
│   ├── graph.py               # LangGraph graph definition + compile()
│   ├── state.py               # InvestigationState TypedDict
│   ├── nodes/
│   │   ├── intake.py
│   │   ├── investigate.py
│   │   ├── dispatch.py
│   │   ├── technical.py
│   │   ├── compliance.py
│   │   └── resolution.py
│   └── tools/
│       ├── payment_tools.py   # get_payment_record, get_resolution_history
│       ├── technical_tools.py # validate_iban, validate_bic, check_duplicate, check_fx
│       └── compliance_tools.py# screen_entity, check_address_completeness
├── routers/
│   ├── exceptions.py          # GET /api/exceptions, POST /api/ingest/exceptions
│   │                          # POST /api/exceptions/{msg_id}/investigate (SSE)
│   └── resolutions.py         # approve / reject
└── db.py                      # _get_db(), _ensure_schema() — extracted from main.py
```

---

## Responsible AI

- **Human-in-the-loop:** Resolution agent produces a recommendation only. No payment action executes without explicit approve/reject from the analyst.
- **Audit trail:** Every step written to `investigations.steps` with timestamp. Full tool call inputs/outputs recorded.
- **Explainability:** Every recommendation includes plain-English rationale and lists all tools/data consulted.
- **False positives:** Compliance agent flags uncertainty explicitly; escalates rather than auto-rejects when confidence is low.