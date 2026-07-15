# pacs008-generator

CBPR+ pacs.008 message generator for the Vista Hackathon (Use Case A — SWIFT
Exceptions & Investigations). Generates a configurable number of messages,
with a configurable share containing random **business errors** from an
extensible error catalog.

**Design principle:** All messages — including the faulty ones — are
**XSD-valid** against the official CBPR+ SR2025 schemas (`schemas/`). Injected
errors are business errors (IBAN check digits, BIC↔IBAN mismatch, incomplete
beneficiary, …) as they trigger downstream exceptions in reality. Every error
is detectable **without external or simulated systems**. Every generated
message is automatically validated against the XSDs before output.

## Quickstart

```bash
pip install -r requirements.txt

# 20 messages, 30% faulty, reproducible
python -m pacs008_generator --count 20 --error-rate 0.3 --seed 42

# or absolute: exactly 5 faulty out of 20
python -m pacs008_generator --count 20 --faulty 5

# show the error catalog / restrict to specific errors
python -m pacs008_generator --list-errors
python -m pacs008_generator --count 10 --errors IBAN_INVALID_CHECKSUM DUPLICATE_UETR
```

Output: `output/NNN_pacs008_{OK|FAULTY}.xml` + **`manifest.json`** (ground
truth: which file carries which error). All errors are detectable from the
message or the batch itself — no simulated reference systems.

## Duplicate-check-free (uniqueness guarantees)

Generated messages pass common duplicate-detection rules: unique UETR (UUID v4,
enforced per batch), MsgId/InstrId/EndToEndId unique across runs via a run ID
(timestamp-based; deterministic when a seed is given), and no business
duplicates (the combination debtor account / creditor account / amount /
currency / value date never repeats). A self-check runs over the whole batch
before output. The only intended exception is the injected `DUPLICATE_UETR`
error.

## Demo UI + API

```bash
uvicorn pacs008_generator.api:app --port 8080
# UI:      http://localhost:8080/
# Swagger: http://localhost:8080/docs
```

UI: count, error rate % or absolute faulty count, seed, error-type selection →
generate → result table (file/status/error/detail), click a row to view the
XML, "Open output folder" opens `output/ui-runs/<run_id>/` in Finder.

Endpoints:
- `GET /errors` — error catalog (for the UI checkbox list)
- `POST /generate` — `{"count": 20, "error_rate": 0.3, "faulty": null, "seed": 42, "error_codes": null, "include_xml": true, "write_files": true}`
  → manifest incl. XML, writes files to `output/ui-runs/<run_id>/`
- `POST /runs/{run_id}/open` — opens the run folder (local demo)

## Structure

```
pacs008_generator/
  datapool.py        reference data (agents, parties, mod-97 IBAN construction)
  builder.py         XML construction (AppHdr head.001.001.02 + Document pacs.008.001.08)
  errors.py          error injectors (mutate the tx dict before XML build)
  validator.py       XSD validation (CBPR+ SR2025)
  generator.py       batch orchestration + manifest
  iban_validator.py  worldwide IBAN validator (ISO 13616, 89 countries)
  __main__.py        CLI
  api.py             FastAPI wrapper + demo UI
error_catalog.yaml         generator error catalog (8 business errors)
agent_error_knowledge.yaml detection rules per error for the AI agent
ERROR_LIST_EN.md           compact review document
schemas/                   official CBPR+ XSDs (MyStandards — internal use!)
aws/                       AWS Lambda deployment (handler, build script)
tests/                     pytest suite (23 tests)
```

## Extending the error catalog

1. Add an entry to `error_catalog.yaml` (code, title, category, severity, injector)
2. Register an injector function in `errors.py` via `@injector("name")` —
   it mutates the `tx` dict and returns a detail string for the manifest
3. Run `pytest` — `test_every_injector_stays_schema_valid` automatically
   checks every catalog entry for XSD conformance

## Tests

```bash
python -m pytest tests/ -v
```

Covered: XSD validity of all outputs, error rate & manifest consistency, seed
reproducibility, error-code filter, every injector individually, uniqueness
guarantees, IBAN validator (worldwide), file/manifest output, error handling.

## Notes

- Python ≥ 3.9, no network access at runtime (AWS-ready, air-gapped ok)
- `schemas/` is subject to the Swift MyStandards licence — internal use only
- BizSvc `swift.cbprplus.03` (SR2025); transport envelope is the sender's concern
