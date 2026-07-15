# Eval Harness Design — PayInvestigator

**Date:** 2026-07-14  
**Scope:** Backend eval harness for the LangGraph multi-agent investigation pipeline

---

## Goal

Replace ad-hoc manual smoke-testing of the 3 demo scenarios with a reproducible, scored eval harness that:

1. Catches graph wiring and routing regressions fast (no LLM, runs in CI / every `pytest` invocation)
2. Validates end-to-end LLM output quality for the 3 demo scenarios before the demo

---

## Two Test Surfaces

### Surface 1 — Fast routing tests (`pytest`)

**File:** `backend/tests/test_agent_routing.py`

Patches `ChatBedrock.ainvoke` with `unittest.mock.AsyncMock` returning minimal canned JSON. Runs the real LangGraph graph. Asserts:

- `intake_classification.needs_technical` and `needs_compliance` match expected values per error code set
- `recommendation` contains keys: `action`, `rationale`, `confidence`, `requires_human_approval`
- `requires_human_approval` is always `True`
- `steps` list is non-empty and each entry has `agent`, `cls`, `text`, `ts` keys

**Invocation:** `pytest tests/test_agent_routing.py` — included in the normal `pytest` run. Target: ~2 seconds.

**Coverage:** 3 test cases (one per demo scenario error set) + 1 structural invariant test.

---

### Surface 2 — Full eval suite (`eval/`)

**Entry point:** `cd backend && python -m eval.report`

Hits real AWS Bedrock. Runs all 3 fixtures end-to-end through the graph. Prints a scored table. Not in CI — run manually before the demo or after significant agent changes.

**Target runtime:** ~60–90 seconds for all 3 scenarios.

---

## File Layout

```
backend/
├── tests/
│   └── test_agent_routing.py      ← NEW
└── eval/
    ├── __init__.py
    ├── fixtures/
    │   ├── bad_iban.json
    │   ├── sanctions_hit.json
    │   └── duplicate_payment.json
    ├── runner.py
    ├── scorer.py
    └── report.py                  ← entry point: python -m eval.report
```

---

## Fixture Format

Each fixture is a valid `InvestigationState`-compatible dict with an injected `_meta` block. The runner strips `_meta` before passing state to the graph.

```json
{
  "_meta": {
    "scenario": "bad_iban",
    "expected_routing": {
      "needs_technical": true,
      "needs_compliance": false
    },
    "required_keywords": ["IBAN", "correct", "resubmit"],
    "min_confidence": 0.75
  },
  "payment": {
    "tx_id": "TX-001",
    "amount": 10000.00,
    "currency": "USD",
    "sender_bic": "DEUTDEDB",
    "receiver_bic": "NWBKGB2L",
    "sender_iban": "DE89370400440532013000",
    "receiver_iban": "GB29NWBK60161331926820",
    "status": "EXCEPTION",
    "error_code": "IBAN_INVALID_CHECKSUM",
    "timestamp": "2026-07-14T08:00:00Z"
  },
  "detected_errors": [
    { "code": "IBAN_INVALID_CHECKSUM", "field": "receiver_iban", "value": "GB29NWBK60161331926820" }
  ],
  "swift_message": "<pacs.008 stub>",
  "steps": [],
  "investigation_id": 1,
  "msg_id": "MSG-001",
  "investigation_context": {},
  "intake_classification": {},
  "technical_findings": null,
  "compliance_findings": null,
  "recommendation": null
}
```

### Fixture keyword tables

| Scenario | `required_keywords` | `min_confidence` | `expected_routing` |
|---|---|---|---|
| `bad_iban` | `["IBAN", "correct", "resubmit"]` | 0.75 | `technical=true, compliance=false` |
| `sanctions_hit` | `["hold", "sanction"]` | 0.80 | `technical=false, compliance=true` |
| `duplicate_payment` | `["duplicate", "cancel"]` | 0.75 | `technical=true, compliance=false` |

---

## Scorer: 3 Checks Per Scenario

| Check | What it tests | Pass criteria |
|---|---|---|
| **Routing** | `state.intake_classification.needs_technical` / `needs_compliance` | Exact match against `_meta.expected_routing` |
| **Structure** | `recommendation` has `action`, `rationale`, `confidence`, `requires_human_approval: true` | All keys present; `requires_human_approval` is boolean `true` |
| **Keywords + Confidence** | `action` or `rationale` contains ≥1 required keyword (case-insensitive); `confidence ≥ min_confidence` | Both sub-checks must pass |

A scenario is `PASS` only if all 3 checks pass.

---

## Report Output

```
PayInvestigator Eval Harness — 2026-07-14T08:00:00Z
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Scenario              Routing    Structure    Keywords    Confidence    Result
bad_iban              ✓          ✓            ✓           0.92          PASS
sanctions_hit         ✓          ✓            ✓           0.88          PASS
duplicate_payment     ✓          ✓            ✗           0.61          FAIL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
2/3 scenarios passed
```

On any `FAIL`, the report prints the failing checks and the actual recommendation text beneath the table for debugging.

---

## Data Flow

```
report.py
  └── runner.py
        ├── loads fixture JSON
        ├── strips _meta
        ├── asyncio.run(graph.ainvoke(state))   ← reuses build_graph() + make_llm()
        └── returns EvalResult dataclass
              { scenario, final_state, routing_pass, structure_pass,
                keyword_pass, confidence, errors[] }
  └── scorer.py
        └── score(fixture_meta, final_state) → EvalResult (fills pass flags)
  └── prints table
```

`runner.py` imports `build_graph` and `make_llm` directly from `agents.graph` — no duplication of graph construction logic.

---

## EvalResult Dataclass

```python
@dataclass
class EvalResult:
    scenario: str
    routing_pass: bool
    structure_pass: bool
    keyword_pass: bool
    confidence: float | None
    errors: list[str]           # human-readable failure reasons

    @property
    def passed(self) -> bool:
        return self.routing_pass and self.structure_pass and self.keyword_pass
```

---

## What Is Not In Scope

- LLM-as-judge semantic scoring (Option C — deferred post-hackathon)
- CI integration for the real-LLM eval suite (credentials management overhead)
- Performance/latency tracking per node
- Scenario coverage beyond the 3 demo scenarios

---

## Invocation Summary

| Command | When to run | LLM calls | Time |
|---|---|---|---|
| `pytest tests/` | Every commit | None (mocked) | ~2s |
| `python -m eval.report` | Before demo; after agent changes | 3 full graph runs | ~90s |
