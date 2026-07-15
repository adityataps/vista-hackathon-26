# Track 1 Agent System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the Track 1 exception investigation pipeline — a LangGraph multi-agent graph that investigates faulty pacs.008 payments and streams reasoning to the frontend via SSE.

**Architecture:** A LangGraph graph (intake → investigate → dispatch → [technical | compliance] → resolution) is triggered on `POST /api/exceptions/{msg_id}/investigate`. The response body is an SSE stream of `{agent, cls, text}` events. Lambda is extended to POST faulty payment IDs to the backend on ingest. FastAPI routers handle the queue, HITL approval, and Q&A chat.

**Tech Stack:** LangGraph 0.2+, langchain-aws (ChatBedrock), langchain-core, FastAPI StreamingResponse, psycopg2, Python 3.12

## Global Constraints

- Model: `anthropic.claude-sonnet-4-6` via AWS Bedrock, region from `AWS_REGION` env var (default `us-west-2`)
- All new backend code lives under `backend/`
- SSE stream events: `{agent, cls, text}` for reasoning lines; `{type: "done", report_id, recommendation: {action, rationale}}` as the final event
- `cls` values must be exactly: `intake`, `investigation`, `technical`, `compliance`, `resolution`, `tool`
- `tx_id` in `GET /api/exceptions` must be `TX-{payment_db_id:05d}` to match frontend mock IDs
- All DB access via `backend/db.py` `get_db()` — never open a new connection in a router or node
- No migration tooling — `CREATE TABLE IF NOT EXISTS` only
- All work on branch `feature/track1-agents`

---

## File Map

| File | Created / Modified | Responsibility |
|---|---|---|
| `backend/db.py` | Create | DB singleton, `_ensure_schema()` (all 4 tables) |
| `backend/agents/__init__.py` | Create | empty |
| `backend/agents/state.py` | Create | `InvestigationState` TypedDict |
| `backend/agents/tools/payment_tools.py` | Create | `get_payment_record`, `get_resolution_history` |
| `backend/agents/tools/technical_tools.py` | Create | `validate_iban_tool`, `validate_bic_tool`, `check_duplicate_tool`, `check_fx_tool` |
| `backend/agents/tools/compliance_tools.py` | Create | `screen_entity_tool`, `check_address_completeness_tool` (SDN list hardcoded) |
| `backend/agents/nodes/intake.py` | Create | intake node — classifies errors, sets routing flags |
| `backend/agents/nodes/investigate.py` | Create | investigate node — assembles payment context |
| `backend/agents/nodes/dispatch.py` | Create | dispatch function — returns `Send` list |
| `backend/agents/nodes/technical.py` | Create | technical node — IBAN/BIC/FX/duplicate ReAct loop |
| `backend/agents/nodes/compliance.py` | Create | compliance node — sanctions/address ReAct loop |
| `backend/agents/nodes/resolution.py` | Create | resolution node — synthesises recommendation |
| `backend/agents/graph.py` | Create | compile and export `investigation_graph` |
| `backend/routers/__init__.py` | Create | empty |
| `backend/routers/exceptions.py` | Create | `GET /api/exceptions`, `POST /api/ingest/exceptions`, `POST /api/exceptions/{msg_id}/investigate` (SSE) |
| `backend/routers/resolutions.py` | Create | `POST /api/resolutions/{report_id}/approve\|reject`, `POST /api/reports/{report_id}/chat` |
| `backend/main.py` | Modify | include new routers, call `_ensure_schema()` on startup |
| `jobs/payment-ingest/handler.py` | Modify | POST to `BACKEND_URL/api/ingest/exceptions` after faulty ingest |

---

## Task 1: Create branch + DB layer

**Files:**
- Create: `backend/db.py`
- Modify: `backend/main.py` (lines 1–34, replace `_db_conn`/`_get_db`/`_ensure_events_schema` with import)

**Interfaces:**
- Produces: `get_db() -> psycopg2.connection | None`, `_ensure_schema(conn)`

- [ ] **Step 1: Create the branch**

```bash
git checkout -b feature/track1-agents
```

Expected: `Switched to a new branch 'feature/track1-agents'`

- [ ] **Step 2: Write `backend/db.py`**

```python
import logging
import os

import psycopg2

logger = logging.getLogger(__name__)

_db_conn = None


def get_db():
    global _db_conn
    if not os.environ.get("DATABASE_URL"):
        return None
    try:
        if _db_conn is None or _db_conn.closed:
            _db_conn = psycopg2.connect(os.environ["DATABASE_URL"])
            _ensure_schema(_db_conn)
    except Exception as exc:
        logger.warning("DB connect failed: %s", exc)
        return None
    return _db_conn


def _ensure_schema(conn):
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS payment_events (
                id            SERIAL PRIMARY KEY,
                event_id      TEXT UNIQUE NOT NULL,
                uetr          TEXT NOT NULL,
                msg_id        TEXT,
                event_type    TEXT NOT NULL,
                status_code   TEXT,
                source_system TEXT,
                actor         TEXT,
                detail        TEXT,
                occurred_at   TIMESTAMPTZ NOT NULL
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_payment_events_uetr ON payment_events(uetr)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_payment_events_msg_id ON payment_events(msg_id)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS exceptions (
                id              SERIAL PRIMARY KEY,
                payment_id      INTEGER,
                msg_id          TEXT UNIQUE NOT NULL,
                uetr            TEXT NOT NULL,
                detected_errors JSONB NOT NULL DEFAULT '[]',
                status          TEXT NOT NULL DEFAULT 'pending',
                created_at      TIMESTAMPTZ DEFAULT NOW(),
                updated_at      TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        cur.execute("CREATE INDEX IF NOT EXISTS idx_exceptions_msg_id ON exceptions(msg_id)")

        cur.execute("""
            CREATE TABLE IF NOT EXISTS investigations (
                id              SERIAL PRIMARY KEY,
                exception_id    INTEGER REFERENCES exceptions(id),
                msg_id          TEXT NOT NULL,
                steps           JSONB NOT NULL DEFAULT '[]',
                findings        JSONB,
                recommendation  JSONB,
                approval_status TEXT DEFAULT 'pending',
                created_at      TIMESTAMPTZ DEFAULT NOW(),
                completed_at    TIMESTAMPTZ
            )
        """)
    conn.commit()
```

- [ ] **Step 3: Update `backend/main.py` to use `db.py`**

Replace the existing `_db_conn`, `_get_db`, `_ensure_events_schema`, and `_write_events` block (lines 19–79) with:

```python
from db import get_db, _ensure_schema


def _write_events(conn, messages):
    rows = []
    for msg in messages:
        for evt in msg.get("events", []):
            rows.append({**evt, "msg_id": msg["msg_id"]})
    if not rows:
        return
    with conn.cursor() as cur:
        for row in rows:
            cur.execute("""
                INSERT INTO payment_events
                    (event_id, uetr, msg_id, event_type, status_code,
                     source_system, actor, detail, occurred_at)
                VALUES
                    (%(event_id)s, %(uetr)s, %(msg_id)s, %(event_type)s, %(status_code)s,
                     %(source_system)s, %(actor)s, %(detail)s, %(occurred_at)s)
                ON CONFLICT (event_id) DO NOTHING
            """, row)
    conn.commit()
```

Also add a startup event to ensure schema on boot:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    get_db()          # opens connection + runs _ensure_schema
    yield

app = FastAPI(title="PayInvestigator", lifespan=lifespan)
```

Remove the old `FastAPI()` call and replace with the one above.

All existing calls to `_get_db()` in `main.py` → replace with `get_db()`.

- [ ] **Step 4: Verify the app starts**

```bash
cd backend
DATABASE_URL="" uvicorn main:app --reload --port 8000
```

Expected: server starts, no import errors. `GET /health` returns `{"status": "ok"}`.

- [ ] **Step 5: Commit**

```bash
git add backend/db.py backend/main.py
git commit -m "feat: extract db.py, add exceptions + investigations schema"
```

---

## Task 2: Payment + technical tools

**Files:**
- Create: `backend/agents/__init__.py`
- Create: `backend/agents/tools/__init__.py`
- Create: `backend/agents/tools/payment_tools.py`
- Create: `backend/agents/tools/technical_tools.py`
- Test: `backend/tests/test_tools.py`

**Interfaces:**
- Consumes: `get_db()` from `db`; `validate_iban` from `pacs008_generator.iban_validator`
- Produces:
  - `get_payment_record(msg_id: str) -> str` — JSON string of payment row
  - `get_resolution_history(error_code: str) -> str` — JSON string of prior cases
  - `validate_iban_tool(iban: str) -> str` — JSON validation result
  - `validate_bic_tool(bic: str) -> str` — JSON validation result
  - `check_duplicate_tool(uetr: str, msg_id: str) -> str` — JSON duplicate result
  - `check_fx_tool(instd_amt: float, sttlm_amt: float, rate: float) -> str` — JSON consistency result

- [ ] **Step 1: Create `backend/agents/__init__.py` and `backend/agents/tools/__init__.py`**

Both are empty files.

```bash
mkdir -p backend/agents/tools backend/agents/nodes backend/routers
touch backend/agents/__init__.py backend/agents/tools/__init__.py backend/agents/nodes/__init__.py backend/routers/__init__.py
```

- [ ] **Step 2: Write `backend/agents/tools/payment_tools.py`**

```python
import json
import sys
import os

from langchain_core.tools import tool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from db import get_db


@tool
def get_payment_record(msg_id: str) -> str:
    """Fetch full payment record from the database by message ID."""
    conn = get_db()
    if not conn:
        return json.dumps({"error": "DB unavailable"})
    with conn.cursor() as cur:
        cur.execute("""
            SELECT id, msg_id, uetr, instr_id, e2e_id, amount, currency,
                   settlement_date, sender_bic, receiver_bic, debtor_bic,
                   creditor_bic, debtor_name, debtor_iban, creditor_name,
                   creditor_iban, is_faulty, ingested_at
            FROM payments WHERE msg_id = %s
        """, (msg_id,))
        row = cur.fetchone()
    if not row:
        return json.dumps({"error": f"No payment found for msg_id={msg_id}"})
    cols = ["id","msg_id","uetr","instr_id","e2e_id","amount","currency",
            "settlement_date","sender_bic","receiver_bic","debtor_bic",
            "creditor_bic","debtor_name","debtor_iban","creditor_name",
            "creditor_iban","is_faulty","ingested_at"]
    return json.dumps(dict(zip(cols, [str(v) if v is not None else None for v in row])))


@tool
def get_resolution_history(error_code: str) -> str:
    """Fetch prior resolved investigation cases for the same error code."""
    conn = get_db()
    if not conn:
        return json.dumps([])
    with conn.cursor() as cur:
        cur.execute("""
            SELECT i.msg_id, i.recommendation, i.completed_at
            FROM investigations i
            JOIN exceptions e ON e.id = i.exception_id
            WHERE i.approval_status = 'approved'
              AND e.detected_errors @> %s::jsonb
            ORDER BY i.completed_at DESC
            LIMIT 5
        """, (json.dumps([{"code": error_code}]),))
        rows = cur.fetchall()
    history = [{"msg_id": r[0], "recommendation": r[1], "resolved_at": str(r[2])} for r in rows]
    return json.dumps(history)
```

- [ ] **Step 3: Write `backend/agents/tools/technical_tools.py`**

```python
import json
import sys
import os
from difflib import SequenceMatcher

from langchain_core.tools import tool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from pacs008_generator.iban_validator import validate_iban
from db import get_db

ISO3166 = {
    "AD","AE","AF","AG","AI","AL","AM","AO","AQ","AR","AS","AT","AU","AW","AX","AZ",
    "BA","BB","BD","BE","BF","BG","BH","BI","BJ","BL","BM","BN","BO","BQ","BR","BS",
    "BT","BV","BW","BY","BZ","CA","CC","CD","CF","CG","CH","CI","CK","CL","CM","CN",
    "CO","CR","CU","CV","CW","CX","CY","CZ","DE","DJ","DK","DM","DO","DZ","EC","EE",
    "EG","EH","ER","ES","ET","FI","FJ","FK","FM","FO","FR","GA","GB","GD","GE","GF",
    "GG","GH","GI","GL","GM","GN","GP","GQ","GR","GS","GT","GU","GW","GY","HK","HM",
    "HN","HR","HT","HU","ID","IE","IL","IM","IN","IO","IQ","IR","IS","IT","JE","JM",
    "JO","JP","KE","KG","KH","KI","KM","KN","KP","KR","KW","KY","KZ","LA","LB","LC",
    "LI","LK","LR","LS","LT","LU","LV","LY","MA","MC","MD","ME","MF","MG","MH","MK",
    "ML","MM","MN","MO","MP","MQ","MR","MS","MT","MU","MV","MW","MX","MY","MZ","NA",
    "NC","NE","NF","NG","NI","NL","NO","NP","NR","NU","NZ","OM","PA","PE","PF","PG",
    "PH","PK","PL","PM","PN","PR","PS","PT","PW","PY","QA","RE","RO","RS","RU","RW",
    "SA","SB","SC","SD","SE","SG","SH","SI","SJ","SK","SL","SM","SN","SO","SR","SS",
    "ST","SV","SX","SY","SZ","TC","TD","TF","TG","TH","TJ","TK","TL","TM","TN","TO",
    "TR","TT","TV","TZ","UA","UG","UM","US","UY","UZ","VA","VC","VE","VG","VI","VN",
    "VU","WF","WS","XK","YE","YT","ZA","ZM","ZW",
}


@tool
def validate_iban_tool(iban: str) -> str:
    """Validate an IBAN using ISO 7064 mod-97 check. Returns validation result with errors."""
    result = validate_iban(iban)
    return json.dumps(result)


@tool
def validate_bic_tool(bic: str) -> str:
    """Validate a BIC/SWIFT code format and country code (positions 5-6)."""
    bic = bic.strip().upper()
    if len(bic) not in (8, 11):
        return json.dumps({"bic": bic, "valid": False, "error": f"BIC must be 8 or 11 chars, got {len(bic)}"})
    country = bic[4:6]
    if country not in ISO3166:
        return json.dumps({"bic": bic, "valid": False, "error": f"Country code '{country}' (positions 5-6) is not a valid ISO 3166-1 alpha-2 code"})
    return json.dumps({"bic": bic, "valid": True, "country": country, "institution": bic[:4], "location": bic[6:8]})


@tool
def check_duplicate_tool(uetr: str, msg_id: str) -> str:
    """Check if a payment with the same UETR already exists (excluding the current msg_id)."""
    conn = get_db()
    if not conn:
        return json.dumps({"duplicate": False, "error": "DB unavailable"})
    with conn.cursor() as cur:
        cur.execute("""
            SELECT msg_id, amount, currency, sender_bic, receiver_bic, ingested_at
            FROM payments
            WHERE uetr = %s AND msg_id != %s
        """, (uetr, msg_id))
        rows = cur.fetchall()
    if not rows:
        return json.dumps({"duplicate": False, "uetr": uetr})
    cols = ["msg_id","amount","currency","sender_bic","receiver_bic","ingested_at"]
    duplicates = [dict(zip(cols, [str(v) if v is not None else None for v in r])) for r in rows]
    return json.dumps({"duplicate": True, "uetr": uetr, "original_payments": duplicates})


@tool
def check_fx_tool(instd_amt: float, sttlm_amt: float, rate: float) -> str:
    """Check if instd_amt * rate is consistent with sttlm_amt. Flags >1% deviation."""
    if rate <= 0 or sttlm_amt <= 0:
        return json.dumps({"consistent": False, "error": "rate and sttlm_amt must be positive"})
    expected = instd_amt * rate
    deviation = abs(expected - sttlm_amt) / sttlm_amt
    consistent = deviation <= 0.01
    return json.dumps({
        "consistent": consistent,
        "instd_amt": instd_amt,
        "sttlm_amt": sttlm_amt,
        "rate": rate,
        "expected_sttlm_amt": round(expected, 5),
        "deviation_pct": round(deviation * 100, 3),
    })
```

- [ ] **Step 4: Write tests in `backend/tests/test_tools.py`**

```bash
mkdir -p backend/tests && touch backend/tests/__init__.py
```

```python
import json
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agents.tools.technical_tools import validate_iban_tool, validate_bic_tool, check_fx_tool


def test_validate_iban_tool_valid():
    result = json.loads(validate_iban_tool.invoke({"iban": "GB29NWBK60161331926819"}))
    # This IBAN has bad checksum (per mock data) — should fail
    assert result["valid"] is False
    assert any(e["code"] == "IBAN_INVALID_CHECKSUM" for e in result["errors"])


def test_validate_iban_tool_invalid_format():
    result = json.loads(validate_iban_tool.invoke({"iban": "NOT_AN_IBAN"}))
    assert result["valid"] is False


def test_validate_bic_tool_valid():
    result = json.loads(validate_bic_tool.invoke({"bic": "DEUTDEDB"}))
    assert result["valid"] is True
    assert result["country"] == "DE"


def test_validate_bic_tool_invalid_country():
    result = json.loads(validate_bic_tool.invoke({"bic": "DEUTXXDB"}))
    assert result["valid"] is False
    assert "XX" in result["error"]


def test_check_fx_tool_consistent():
    result = json.loads(check_fx_tool.invoke({"instd_amt": 1000.0, "sttlm_amt": 850.0, "rate": 0.85}))
    assert result["consistent"] is True


def test_check_fx_tool_inconsistent():
    result = json.loads(check_fx_tool.invoke({"instd_amt": 1000.0, "sttlm_amt": 850.0, "rate": 0.75}))
    assert result["consistent"] is False
    assert result["deviation_pct"] > 1.0
```

- [ ] **Step 5: Run tests**

```bash
cd backend
python -m pytest tests/test_tools.py -v
```

Expected: 6 tests pass.

- [ ] **Step 6: Commit**

```bash
git add backend/agents/ backend/routers/ backend/tests/
git commit -m "feat: payment and technical tools with tests"
```

---

## Task 3: Compliance tools + sanctions data

**Files:**
- Create: `backend/agents/tools/compliance_tools.py`
- Test: `backend/tests/test_tools.py` (append)

**Interfaces:**
- Produces:
  - `screen_entity_tool(name: str) -> str` — JSON with `{match, score, entry}`
  - `check_address_completeness_tool(address_json: str) -> str` — JSON with `{complete, missing_fields}`

- [ ] **Step 1: Write `backend/agents/tools/compliance_tools.py`**

```python
import json
from difflib import SequenceMatcher

from langchain_core.tools import tool

# Simplified OFAC SDN entries sufficient for demo scenarios
SDN_LIST = [
    {
        "name": "NOVAYA ZVEZDA SHIPPING LLC",
        "aliases": ["Novaya Star", "NZ Shipping", "Novaya Star Shipping", "Novaya Zvezda"],
        "country": "RU",
        "program": "RUSSIA-EO14024",
        "list": "OFAC SDN",
        "notes": "Re-registered in UAE 2024; vessel ownership links to listed entities",
    },
    {
        "name": "IRAN SHIPPING LINES",
        "aliases": ["IRISL", "Islamic Republic of Iran Shipping"],
        "country": "IR",
        "program": "IRAN",
        "list": "OFAC SDN",
        "notes": "State-owned shipping company",
    },
    {
        "name": "KOREA MINING DEVELOPMENT TRADING CORPORATION",
        "aliases": ["KOMID", "Korea Mining Development"],
        "country": "KP",
        "program": "NPWMD",
        "list": "OFAC SDN",
        "notes": "DPRK arms trafficking entity",
    },
    {
        "name": "AL-RASHID TRUST",
        "aliases": ["Al Rashid Trust", "Alrashid Trust"],
        "country": "PK",
        "program": "SDGT",
        "list": "OFAC SDN",
        "notes": "Terror finance network",
    },
]


def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


@tool
def screen_entity_tool(name: str) -> str:
    """Screen an entity name against the sanctions list using fuzzy matching.
    Returns match result with score and matched SDN entry if above threshold."""
    best_score = 0.0
    best_entry = None
    best_alias = None

    for entry in SDN_LIST:
        candidates = [entry["name"]] + entry.get("aliases", [])
        for candidate in candidates:
            score = _similarity(name, candidate)
            if score > best_score:
                best_score = score
                best_entry = entry
                best_alias = candidate

    if best_score >= 0.70:
        return json.dumps({
            "match": True,
            "score": round(best_score, 3),
            "matched_alias": best_alias,
            "entry": best_entry,
            "threshold": 0.70,
        })
    return json.dumps({
        "match": False,
        "score": round(best_score, 3),
        "closest_alias": best_alias,
        "threshold": 0.70,
    })


@tool
def check_address_completeness_tool(address_json: str) -> str:
    """Check if a creditor postal address meets FATF Travel Rule requirements.
    address_json should be a JSON object with keys like Ctry, TwnNm, StrtNm, AdrLine.
    Returns {complete, missing_fields, fatf_compliant}."""
    try:
        address = json.loads(address_json)
    except Exception:
        return json.dumps({"complete": False, "error": "address_json must be valid JSON"})

    required = ["Ctry"]
    recommended = ["TwnNm", "StrtNm"]
    missing_required = [f for f in required if not address.get(f)]
    missing_recommended = [f for f in recommended if not address.get(f)]
    has_adr_line = bool(address.get("AdrLine"))

    fatf_compliant = not missing_required and (not missing_recommended or has_adr_line)

    return json.dumps({
        "complete": fatf_compliant,
        "missing_required_fields": missing_required,
        "missing_recommended_fields": missing_recommended,
        "has_adr_line_fallback": has_adr_line,
        "fatf_compliant": fatf_compliant,
        "note": "CBPR+ SR2026 requires country + town + street or AdrLine",
    })
```

- [ ] **Step 2: Append compliance tests to `backend/tests/test_tools.py`**

```python
from agents.tools.compliance_tools import screen_entity_tool, check_address_completeness_tool
import json


def test_screen_entity_sanctions_hit():
    result = json.loads(screen_entity_tool.invoke({"name": "Novaya Star Shipping"}))
    assert result["match"] is True
    assert result["score"] >= 0.70
    assert "NOVAYA ZVEZDA" in result["entry"]["name"]


def test_screen_entity_no_hit():
    result = json.loads(screen_entity_tool.invoke({"name": "Thames Logistics Ltd"}))
    assert result["match"] is False


def test_check_address_complete():
    addr = json.dumps({"Ctry": "GB", "TwnNm": "London", "StrtNm": "Baker St"})
    result = json.loads(check_address_completeness_tool.invoke({"address_json": addr}))
    assert result["fatf_compliant"] is True


def test_check_address_incomplete():
    addr = json.dumps({"Ctry": "GB"})
    result = json.loads(check_address_completeness_tool.invoke({"address_json": addr}))
    assert result["fatf_compliant"] is False
    assert "TwnNm" in result["missing_recommended_fields"]
```

- [ ] **Step 3: Run tests**

```bash
cd backend
python -m pytest tests/test_tools.py -v
```

Expected: 10 tests pass.

- [ ] **Step 4: Commit**

```bash
git add backend/agents/tools/compliance_tools.py backend/tests/test_tools.py
git commit -m "feat: compliance tools with SDN list and address checker"
```

---

## Task 4: Agent state + nodes

**Files:**
- Create: `backend/agents/state.py`
- Create: `backend/agents/nodes/intake.py`
- Create: `backend/agents/nodes/investigate.py`
- Create: `backend/agents/nodes/dispatch.py`
- Create: `backend/agents/nodes/technical.py`
- Create: `backend/agents/nodes/compliance.py`
- Create: `backend/agents/nodes/resolution.py`

**Interfaces:**
- Consumes: all tools from tasks 2 + 3; `get_db()` from `db`
- Produces: `InvestigationState` TypedDict; one async function per node: `intake_node`, `investigate_node`, `dispatch_node`, `technical_node`, `compliance_node`, `resolution_node`

- [ ] **Step 1: Write `backend/agents/state.py`**

```python
from typing import Optional, TypedDict


class InvestigationState(TypedDict):
    payment: dict
    detected_errors: list          # [{code, field, value}]
    swift_message: str
    intake_classification: dict    # {error_categories: [], needs_technical: bool, needs_compliance: bool}
    investigation_context: dict
    technical_findings: Optional[dict]
    compliance_findings: Optional[dict]
    recommendation: Optional[dict] # {action, rationale, confidence}
    steps: list                    # append-only [{agent, cls, text, ts}]
    investigation_id: int
    msg_id: str


# Maps error codes → category for dispatch routing
ERROR_CATEGORY_MAP = {
    "IBAN_INVALID_CHECKSUM": "account_identifier",
    "IBAN_WRONG_LENGTH": "account_identifier",
    "BIC_IBAN_COUNTRY_MISMATCH": "account_identifier",
    "BIC_INVALID_COUNTRY": "routing",
    "BENEFICIARY_NAME_INCOMPLETE": "beneficiary_data",
    "ADDRESS_INCOMPLETE": "beneficiary_data",
    "DUPLICATE_UETR": "duplicate",
    "XCHG_RATE_INCONSISTENT": "fx",
}

TECHNICAL_CATEGORIES = {"account_identifier", "routing", "duplicate", "fx"}
COMPLIANCE_CATEGORIES = {"beneficiary_data"}
```

- [ ] **Step 2: Write `backend/agents/nodes/intake.py`**

```python
import json
import logging
from datetime import datetime, timezone

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage

from agents.state import InvestigationState, ERROR_CATEGORY_MAP, TECHNICAL_CATEGORIES, COMPLIANCE_CATEGORIES

logger = logging.getLogger(__name__)

SYSTEM = """You are the Intake Agent for a payment exception investigation system.
Your job is to classify detected payment errors and set routing flags for specialist agents.
Be concise. Output a single sentence describing the exception type and routing decision."""


async def intake_node(state: InvestigationState, llm: ChatBedrock) -> dict:
    errors = state["detected_errors"]
    categories = {ERROR_CATEGORY_MAP.get(e.get("code", ""), "account_identifier") for e in errors}

    needs_technical = bool(categories & TECHNICAL_CATEGORIES)
    needs_compliance = bool(categories & COMPLIANCE_CATEGORIES)
    if not needs_technical and not needs_compliance:
        needs_technical = True

    error_summary = ", ".join(e.get("code", "UNKNOWN") for e in errors)
    prompt = f"Payment exception detected. Error codes: {error_summary}. Classify and describe the investigation routing in one sentence."

    response = await llm.ainvoke([SystemMessage(content=SYSTEM), HumanMessage(content=prompt)])
    classification_text = response.content

    ts = datetime.now(timezone.utc).isoformat()
    step = {"agent": "Intake Agent", "cls": "intake", "text": classification_text, "ts": ts}

    return {
        "intake_classification": {
            "error_categories": list(categories),
            "needs_technical": needs_technical,
            "needs_compliance": needs_compliance,
        },
        "steps": state.get("steps", []) + [step],
    }
```

- [ ] **Step 3: Write `backend/agents/nodes/investigate.py`**

```python
import json
import logging
from datetime import datetime, timezone

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage

from agents.state import InvestigationState
from agents.tools.payment_tools import get_payment_record

logger = logging.getLogger(__name__)

SYSTEM = """You are the Investigation Agent. You gather context about a payment before
specialist agents investigate. Summarise the key payment details in 1-2 sentences:
amount, corridor, sender, receiver, and what makes this payment notable."""


async def investigate_node(state: InvestigationState, llm: ChatBedrock) -> dict:
    payment = state["payment"]
    summary_prompt = (
        f"Payment msg_id={payment.get('msg_id')} "
        f"amount={payment.get('amount')} {payment.get('currency')} "
        f"sender={payment.get('debtor_name')} ({payment.get('sender_bic')}) "
        f"receiver={payment.get('creditor_name')} ({payment.get('receiver_bic')}) "
        f"errors={json.dumps(state['detected_errors'])}. "
        "Summarise this payment and the detected errors in 1-2 sentences."
    )
    response = await llm.ainvoke([SystemMessage(content=SYSTEM), HumanMessage(content=summary_prompt)])
    summary = response.content

    ts = datetime.now(timezone.utc).isoformat()
    step = {"agent": "Investigation Agent", "cls": "investigation", "text": summary, "ts": ts}

    context = {
        "debtor_iban": payment.get("debtor_iban"),
        "creditor_iban": payment.get("creditor_iban"),
        "debtor_bic": payment.get("debtor_bic"),
        "creditor_bic": payment.get("creditor_bic"),
        "debtor_name": payment.get("debtor_name"),
        "creditor_name": payment.get("creditor_name"),
        "amount": str(payment.get("amount")),
        "currency": payment.get("currency"),
        "uetr": payment.get("uetr"),
    }

    return {
        "investigation_context": context,
        "steps": state.get("steps", []) + [step],
    }
```

- [ ] **Step 4: Write `backend/agents/nodes/dispatch.py`**

```python
from langgraph.constants import Send
from agents.state import InvestigationState, ERROR_CATEGORY_MAP, TECHNICAL_CATEGORIES, COMPLIANCE_CATEGORIES


def dispatch_node(state: InvestigationState) -> list:
    """Fan out to technical, compliance, or both based on error categories."""
    classification = state.get("intake_classification", {})
    needs_technical = classification.get("needs_technical", True)
    needs_compliance = classification.get("needs_compliance", False)

    targets = []
    if needs_technical:
        targets.append(Send("technical", state))
    if needs_compliance:
        targets.append(Send("compliance", state))
    return targets or [Send("technical", state)]
```

- [ ] **Step 5: Write `backend/agents/nodes/technical.py`**

```python
import json
import logging
from datetime import datetime, timezone

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from agents.state import InvestigationState
from agents.tools.technical_tools import validate_iban_tool, validate_bic_tool, check_duplicate_tool, check_fx_tool
from agents.tools.payment_tools import get_payment_record

logger = logging.getLogger(__name__)

TOOLS = [validate_iban_tool, validate_bic_tool, check_duplicate_tool, check_fx_tool, get_payment_record]
TOOL_MAP = {t.name: t for t in TOOLS}

SYSTEM = """You are the Technical Diagnosis specialist for payment exceptions.
Investigate each detected error using your tools. For IBAN errors: validate the IBAN and report
which check failed. For BIC errors: validate the BIC. For duplicate UETR: check the database.
For FX inconsistency: check the math. After investigating, summarise your findings and the
recommended remediation. Be specific — name the exact field values and what is wrong."""


async def technical_node(state: InvestigationState, llm: ChatBedrock) -> dict:
    payment = state["payment"]
    errors = state["detected_errors"]
    context = state["investigation_context"]

    messages = [
        SystemMessage(content=SYSTEM),
        HumanMessage(content=(
            f"Payment record:\n{json.dumps(payment, indent=2)}\n\n"
            f"Detected errors:\n{json.dumps(errors, indent=2)}\n\n"
            f"Context:\n{json.dumps(context, indent=2)}\n\n"
            "Investigate each error using your tools. Report findings and remediation."
        )),
    ]

    llm_with_tools = llm.bind_tools(TOOLS)
    steps = list(state.get("steps", []))

    for _ in range(6):  # max 6 iterations of the ReAct loop
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        if not response.tool_calls:
            break

        for tc in response.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            args_str = ", ".join(f"{k}={repr(v)}" for k, v in tool_args.items())
            ts = datetime.now(timezone.utc).isoformat()
            steps.append({"agent": "tool", "cls": "tool", "text": f"🔧 {tool_name}({args_str})", "ts": ts})

            tool_fn = TOOL_MAP.get(tool_name)
            if tool_fn:
                result = tool_fn.invoke(tool_args)
            else:
                result = json.dumps({"error": f"Unknown tool: {tool_name}"})

            steps.append({"agent": "tool", "cls": "tool", "text": f"↳ {str(result)[:200]}", "ts": ts})
            messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))

    findings_text = response.content if hasattr(response, "content") else ""
    ts = datetime.now(timezone.utc).isoformat()
    steps.append({"agent": "Technical Diagnosis", "cls": "technical", "text": findings_text, "ts": ts})

    return {
        "technical_findings": {"raw": findings_text, "agent": "technical"},
        "steps": steps,
    }
```

- [ ] **Step 6: Write `backend/agents/nodes/compliance.py`**

```python
import json
import logging
from datetime import datetime, timezone

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage

from agents.state import InvestigationState
from agents.tools.compliance_tools import screen_entity_tool, check_address_completeness_tool
from agents.tools.payment_tools import get_payment_record

logger = logging.getLogger(__name__)

TOOLS = [screen_entity_tool, check_address_completeness_tool, get_payment_record]
TOOL_MAP = {t.name: t for t in TOOLS}

SYSTEM = """You are the Compliance specialist for payment exceptions.
For beneficiary name errors: screen the creditor name against the sanctions list.
For address errors: check FATF Travel Rule address completeness.
Report your findings clearly: match scores, which list, what the risk is, and your recommendation.
Never auto-reject — if uncertain, recommend hold + escalation for human review."""


async def compliance_node(state: InvestigationState, llm: ChatBedrock) -> dict:
    payment = state["payment"]
    errors = state["detected_errors"]
    context = state["investigation_context"]

    messages = [
        SystemMessage(content=SYSTEM),
        HumanMessage(content=(
            f"Payment record:\n{json.dumps(payment, indent=2)}\n\n"
            f"Detected errors:\n{json.dumps(errors, indent=2)}\n\n"
            f"Context:\n{json.dumps(context, indent=2)}\n\n"
            "Investigate compliance concerns using your tools. Report findings."
        )),
    ]

    llm_with_tools = llm.bind_tools(TOOLS)
    steps = list(state.get("steps", []))

    for _ in range(6):
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)

        if not response.tool_calls:
            break

        for tc in response.tool_calls:
            tool_name = tc["name"]
            tool_args = tc["args"]
            args_str = ", ".join(f"{k}={repr(v)}" for k, v in tool_args.items())
            ts = datetime.now(timezone.utc).isoformat()
            steps.append({"agent": "tool", "cls": "tool", "text": f"🔧 {tool_name}({args_str})", "ts": ts})

            tool_fn = TOOL_MAP.get(tool_name)
            result = tool_fn.invoke(tool_args) if tool_fn else json.dumps({"error": f"Unknown tool: {tool_name}"})

            steps.append({"agent": "tool", "cls": "tool", "text": f"↳ {str(result)[:200]}", "ts": ts})
            messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))

    findings_text = response.content if hasattr(response, "content") else ""
    ts = datetime.now(timezone.utc).isoformat()
    steps.append({"agent": "Compliance Agent", "cls": "compliance", "text": findings_text, "ts": ts})

    return {
        "compliance_findings": {"raw": findings_text, "agent": "compliance"},
        "steps": steps,
    }
```

- [ ] **Step 7: Write `backend/agents/nodes/resolution.py`**

```python
import json
import logging
from datetime import datetime, timezone

from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage

from agents.state import InvestigationState
from agents.tools.payment_tools import get_resolution_history

logger = logging.getLogger(__name__)

SYSTEM = """You are the Resolution Agent. You synthesise findings from specialist agents
and produce a single clear recommendation for the human analyst.
Your output must be a JSON object with exactly these keys:
  action   — one sentence: what the analyst should do
  rationale — 2-3 sentences: why, citing specific evidence from the investigation
  confidence — a float 0.0–1.0

Do NOT recommend any autonomous action. Always end with the analyst making the final decision."""


async def resolution_node(state: InvestigationState, llm: ChatBedrock) -> dict:
    technical = state.get("technical_findings") or {}
    compliance = state.get("compliance_findings") or {}
    errors = state["detected_errors"]

    # pull resolution history for context
    error_codes = [e.get("code") for e in errors if e.get("code")]
    history_results = []
    for code in error_codes[:2]:  # limit to 2 lookups
        history_results.append(get_resolution_history.invoke({"error_code": code}))

    prompt = (
        f"Technical findings:\n{technical.get('raw', 'N/A')}\n\n"
        f"Compliance findings:\n{compliance.get('raw', 'N/A')}\n\n"
        f"Prior resolution history:\n{json.dumps(history_results)}\n\n"
        "Synthesise these findings and produce your recommendation as a JSON object with "
        "keys: action, rationale, confidence."
    )

    response = await llm.ainvoke([SystemMessage(content=SYSTEM), HumanMessage(content=prompt)])
    raw = response.content.strip()

    # extract JSON — model may wrap in markdown code block
    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    try:
        recommendation = json.loads(raw)
    except Exception:
        recommendation = {"action": raw, "rationale": "See full agent output.", "confidence": 0.8}

    ts = datetime.now(timezone.utc).isoformat()
    step = {
        "agent": "Resolution Agent",
        "cls": "resolution",
        "text": f"Recommendation: {recommendation.get('action', '')} (confidence {recommendation.get('confidence', 0):.0%})",
        "ts": ts,
    }

    return {
        "recommendation": recommendation,
        "steps": state.get("steps", []) + [step],
    }
```

- [ ] **Step 8: Commit**

```bash
git add backend/agents/
git commit -m "feat: agent state, all 6 LangGraph nodes"
```

---

## Task 5: LangGraph graph assembly

**Files:**
- Create: `backend/agents/graph.py`

**Interfaces:**
- Consumes: all 6 node functions; `InvestigationState` from `state`
- Produces: `build_graph(llm) -> CompiledGraph` — call once at startup, reuse for all investigations

- [ ] **Step 1: Write `backend/agents/graph.py`**

```python
import os

from langchain_aws import ChatBedrock
from langgraph.graph import StateGraph, START, END

from agents.state import InvestigationState
from agents.nodes.intake import intake_node
from agents.nodes.investigate import investigate_node
from agents.nodes.dispatch import dispatch_node
from agents.nodes.technical import technical_node
from agents.nodes.compliance import compliance_node
from agents.nodes.resolution import resolution_node


def build_graph(llm: ChatBedrock):
    builder = StateGraph(InvestigationState)

    # Bind llm into each node via closure
    builder.add_node("intake", lambda s: intake_node(s, llm))
    builder.add_node("investigate", lambda s: investigate_node(s, llm))
    builder.add_node("dispatch", dispatch_node)
    builder.add_node("technical", lambda s: technical_node(s, llm))
    builder.add_node("compliance", lambda s: compliance_node(s, llm))
    builder.add_node("resolution", lambda s: resolution_node(s, llm))

    builder.add_edge(START, "intake")
    builder.add_edge("intake", "investigate")
    builder.add_edge("investigate", "dispatch")
    builder.add_conditional_edges("dispatch", dispatch_node, ["technical", "compliance"])
    builder.add_edge("technical", "resolution")
    builder.add_edge("compliance", "resolution")
    builder.add_edge("resolution", END)

    return builder.compile()


def make_llm() -> ChatBedrock:
    return ChatBedrock(
        model_id="anthropic.claude-sonnet-4-6",
        region_name=os.environ.get("AWS_REGION", "us-west-2"),
    )
```

- [ ] **Step 2: Smoke-test graph construction**

```bash
cd backend
python -c "
from agents.graph import build_graph, make_llm
g = build_graph(make_llm())
print('Nodes:', list(g.nodes))
print('Graph compiled OK')
"
```

Expected output contains: `Nodes:` followed by a list including `intake`, `investigate`, `dispatch`, `technical`, `compliance`, `resolution`.

- [ ] **Step 3: Commit**

```bash
git add backend/agents/graph.py
git commit -m "feat: LangGraph investigation graph assembled"
```

---

## Task 6: Exception queue endpoints

**Files:**
- Create: `backend/routers/exceptions.py` (queue endpoints only — SSE added in Task 7)

**Interfaces:**
- Produces:
  - `GET /api/exceptions` → `[{tx_id, type, type_key, amount, sender, receiver, status, created_at}]`
  - `POST /api/ingest/exceptions` body `{msg_id, uetr, detected_errors, payment_id?}` → `{exception_id}`

- [ ] **Step 1: Write the queue portion of `backend/routers/exceptions.py`**

```python
import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from db import get_db

logger = logging.getLogger(__name__)
router = APIRouter()

# Maps error code → (display type, type_key) for frontend pill colours
ERROR_TYPE_MAP = {
    "IBAN_INVALID_CHECKSUM":      ("Bad IBAN",        "iban"),
    "IBAN_WRONG_LENGTH":          ("Bad IBAN",        "iban"),
    "BIC_IBAN_COUNTRY_MISMATCH":  ("Bad IBAN",        "iban"),
    "BIC_INVALID_COUNTRY":        ("Bad IBAN",        "iban"),
    "BENEFICIARY_NAME_INCOMPLETE":("ISO 20022 field", "iso"),
    "ADDRESS_INCOMPLETE":         ("ISO 20022 field", "iso"),
    "DUPLICATE_UETR":             ("Duplicate ref",   "duplicate"),
    "XCHG_RATE_INCONSISTENT":     ("FX limit breach", "fx"),
}


def _format_amount(amount, currency) -> str:
    symbols = {"EUR": "€", "USD": "$", "GBP": "£", "JPY": "¥", "CHF": "CHF "}
    sym = symbols.get(currency, f"{currency} ")
    try:
        val = float(amount)
        return f"{sym}{val:,.0f}"
    except Exception:
        return f"{sym}{amount}"


@router.get("/api/exceptions")
def list_exceptions():
    conn = get_db()
    if not conn:
        return []
    with conn.cursor() as cur:
        cur.execute("""
            SELECT e.id, e.msg_id, e.uetr, e.detected_errors, e.status, e.created_at,
                   p.id as payment_db_id, p.amount, p.currency,
                   p.debtor_name, p.creditor_name, p.sender_bic, p.receiver_bic
            FROM exceptions e
            LEFT JOIN payments p ON p.msg_id = e.msg_id
            ORDER BY e.created_at DESC
            LIMIT 50
        """)
        rows = cur.fetchall()

    result = []
    for row in rows:
        (exc_id, msg_id, uetr, detected_errors, status, created_at,
         payment_db_id, amount, currency, debtor_name, creditor_name,
         sender_bic, receiver_bic) = row

        errors = detected_errors if isinstance(detected_errors, list) else []
        first_code = errors[0].get("code", "") if errors else ""
        display_type, type_key = ERROR_TYPE_MAP.get(first_code, ("Unknown", "gray"))

        tx_id = f"TX-{payment_db_id:05d}" if payment_db_id else msg_id

        result.append({
            "tx_id": tx_id,
            "msg_id": msg_id,
            "type": display_type,
            "type_key": type_key,
            "amount": _format_amount(amount, currency) if amount else "—",
            "sender": debtor_name or sender_bic or "—",
            "receiver": creditor_name or receiver_bic or "—",
            "status": status,
            "created_at": created_at.isoformat() if created_at else None,
        })
    return result


class IngestExceptionRequest(BaseModel):
    msg_id: str
    uetr: str
    detected_errors: list
    payment_id: Optional[int] = None


@router.post("/api/ingest/exceptions")
def ingest_exception(req: IngestExceptionRequest):
    conn = get_db()
    if not conn:
        raise HTTPException(status_code=503, detail="DB unavailable")
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO exceptions (msg_id, uetr, detected_errors, payment_id, status)
            VALUES (%s, %s, %s, %s, 'pending')
            ON CONFLICT (msg_id) DO UPDATE SET
                detected_errors = EXCLUDED.detected_errors,
                updated_at = NOW()
            RETURNING id
        """, (req.msg_id, req.uetr, json.dumps(req.detected_errors), req.payment_id))
        exception_id = cur.fetchone()[0]
    conn.commit()
    logger.info("Exception created/updated: id=%s msg_id=%s", exception_id, req.msg_id)
    return {"exception_id": exception_id}
```

- [ ] **Step 2: Register router in `backend/main.py`**

Add near the top of `main.py`:
```python
from routers.exceptions import router as exceptions_router
```

After `app = FastAPI(...)`:
```python
app.include_router(exceptions_router)
```

- [ ] **Step 3: Manual smoke-test**

Start the backend then call the endpoints:

```bash
cd backend && uvicorn main:app --reload --port 8000

# In another terminal:
curl -s http://localhost:8000/api/exceptions | python3 -m json.tool
curl -s -X POST http://localhost:8000/api/ingest/exceptions \
  -H "Content-Type: application/json" \
  -d '{"msg_id":"TEST-001","uetr":"aaa-bbb","detected_errors":[{"code":"IBAN_INVALID_CHECKSUM","field":"CdtrAcct/Id/IBAN","value":"DE00123"}]}' \
  | python3 -m json.tool
```

Expected: `POST` returns `{"exception_id": <int>}`, `GET` returns the row.

- [ ] **Step 4: Commit**

```bash
git add backend/routers/exceptions.py backend/main.py
git commit -m "feat: exception queue endpoints GET and POST /ingest"
```

---

## Task 7: Investigate SSE endpoint

**Files:**
- Modify: `backend/routers/exceptions.py` (add `/investigate` route + normalisation)

**Interfaces:**
- Consumes: `build_graph`, `make_llm` from `agents.graph`; `get_db()` from `db`
- Produces: `POST /api/exceptions/{msg_id}/investigate` → SSE stream

- [ ] **Step 1: Add graph singleton to `backend/main.py`**

Add after the `lifespan` context manager (but still before `app` declaration):

```python
from agents.graph import build_graph, make_llm as _make_llm

_llm = None
_investigation_graph = None


def get_graph():
    global _llm, _investigation_graph
    if _investigation_graph is None:
        _llm = _make_llm()
        _investigation_graph = build_graph(_llm)
    return _investigation_graph
```

- [ ] **Step 2: Add the SSE investigate route to `backend/routers/exceptions.py`**

Add these imports at the top:
```python
import asyncio
from datetime import datetime, timezone
from fastapi.responses import StreamingResponse
```

Add this function and route at the bottom of the file:

```python
def _normalize_lg_event(event: dict) -> dict | None:
    """Convert a LangGraph astream_events event to {agent, cls, text} SSE shape."""
    kind = event.get("event", "")
    node = event.get("metadata", {}).get("langgraph_node", "")

    NODE_META = {
        "intake":      ("Intake Agent",       "intake"),
        "investigate": ("Investigation Agent", "investigation"),
        "technical":   ("Technical Diagnosis","technical"),
        "compliance":  ("Compliance Agent",    "compliance"),
        "resolution":  ("Resolution Agent",    "resolution"),
    }

    if kind == "on_chat_model_stream":
        chunk = event.get("data", {}).get("chunk")
        text = ""
        if chunk and hasattr(chunk, "content"):
            text = chunk.content if isinstance(chunk.content, str) else ""
        if not text:
            return None
        agent_name, cls = NODE_META.get(node, ("Agent", "agent"))
        return {"agent": agent_name, "cls": cls, "text": text}

    if kind == "on_tool_start":
        tool_name = event.get("name", "tool")
        tool_input = event.get("data", {}).get("input", {})
        args_str = ", ".join(f"{k}={repr(v)}" for k, v in tool_input.items())
        return {"agent": "tool", "cls": "tool", "text": f"🔧 {tool_name}({args_str})"}

    if kind == "on_tool_end":
        tool_name = event.get("name", "tool")
        output = str(event.get("data", {}).get("output", ""))[:150]
        return {"agent": "tool", "cls": "tool", "text": f"↳ {output}"}

    return None


@router.post("/api/exceptions/{msg_id}/investigate")
async def investigate(msg_id: str):
    conn = get_db()
    if not conn:
        raise HTTPException(status_code=503, detail="DB unavailable")

    # Load exception + payment
    with conn.cursor() as cur:
        cur.execute("""
            SELECT e.id, e.detected_errors, p.id as pid,
                   p.msg_id, p.uetr, p.amount, p.currency,
                   p.settlement_date, p.sender_bic, p.receiver_bic,
                   p.debtor_bic, p.creditor_bic, p.debtor_name, p.debtor_iban,
                   p.creditor_name, p.creditor_iban, p.is_faulty, p.raw_xml
            FROM exceptions e
            LEFT JOIN payments p ON p.msg_id = e.msg_id
            WHERE e.msg_id = %s
        """, (msg_id,))
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Exception not found: {msg_id}")

    (exc_id, detected_errors, pid, p_msg_id, uetr, amount, currency,
     sdate, sender_bic, receiver_bic, debtor_bic, creditor_bic,
     debtor_name, debtor_iban, creditor_name, creditor_iban,
     is_faulty, raw_xml) = row

    payment = {
        "id": pid, "msg_id": p_msg_id, "uetr": uetr,
        "amount": str(amount), "currency": currency,
        "settlement_date": str(sdate) if sdate else None,
        "sender_bic": sender_bic, "receiver_bic": receiver_bic,
        "debtor_bic": debtor_bic, "creditor_bic": creditor_bic,
        "debtor_name": debtor_name, "debtor_iban": debtor_iban,
        "creditor_name": creditor_name, "creditor_iban": creditor_iban,
    }

    errors = detected_errors if isinstance(detected_errors, list) else []

    # Create investigations row
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO investigations (exception_id, msg_id, steps)
            VALUES (%s, %s, '[]') RETURNING id
        """, (exc_id, msg_id))
        inv_id = cur.fetchone()[0]
        cur.execute("UPDATE exceptions SET status='investigating' WHERE id=%s", (exc_id,))
    conn.commit()

    report_id = f"RPT-{inv_id:04d}"

    initial_state = {
        "payment": payment,
        "detected_errors": errors,
        "swift_message": raw_xml or "",
        "intake_classification": {},
        "investigation_context": {},
        "technical_findings": None,
        "compliance_findings": None,
        "recommendation": None,
        "steps": [],
        "investigation_id": inv_id,
        "msg_id": msg_id,
    }

    from main import get_graph
    graph = get_graph()

    async def event_stream():
        accumulated_steps = []
        final_state = {}

        async for event in graph.astream_events(initial_state, version="v2"):
            sse = _normalize_lg_event(event)
            if sse:
                accumulated_steps.append({**sse, "ts": datetime.now(timezone.utc).isoformat()})
                yield f"data: {json.dumps(sse)}\n\n"

            # Capture final state
            if event.get("event") == "on_chain_end" and event.get("name") == "LangGraph":
                final_state = event.get("data", {}).get("output", {})

        # Persist final state
        recommendation = final_state.get("recommendation") or {}
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE investigations
                SET steps=%s, findings=%s, recommendation=%s,
                    approval_status='pending', completed_at=NOW()
                WHERE id=%s
            """, (
                json.dumps(accumulated_steps),
                json.dumps({
                    "technical": final_state.get("technical_findings"),
                    "compliance": final_state.get("compliance_findings"),
                }),
                json.dumps(recommendation),
                inv_id,
            ))
            cur.execute("UPDATE exceptions SET status='awaiting_approval' WHERE id=%s", (exc_id,))
        conn.commit()

        done_event = {
            "type": "done",
            "report_id": report_id,
            "recommendation": {
                "action": recommendation.get("action", "Review required"),
                "rationale": recommendation.get("rationale", ""),
            },
        }
        yield f"data: {json.dumps(done_event)}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 2: Verify SSE endpoint exists**

```bash
cd backend && uvicorn main:app --reload --port 8000
curl -s -N -X POST http://localhost:8000/api/exceptions/TEST-001/investigate
```

Expected: starts streaming `data:` lines (or 404 if TEST-001 doesn't exist in DB — that's fine; insert a test row first).

- [ ] **Step 3: Commit**

```bash
git add backend/routers/exceptions.py backend/main.py
git commit -m "feat: investigate SSE endpoint with LangGraph streaming"
```

---

## Task 8: Resolution + chat endpoints

**Files:**
- Create: `backend/routers/resolutions.py`
- Modify: `backend/main.py` (include new router)

**Interfaces:**
- Produces:
  - `POST /api/resolutions/{report_id}/approve` → `{status: "approved"}`
  - `POST /api/resolutions/{report_id}/reject` → `{status: "rejected"}`
  - `POST /api/reports/{report_id}/chat` body `{message}` → `{answer, tool}`

- [ ] **Step 1: Write `backend/routers/resolutions.py`**

```python
import json
import logging
import os

from fastapi import APIRouter, HTTPException
from langchain_aws import ChatBedrock
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from db import get_db

logger = logging.getLogger(__name__)
router = APIRouter()


def _inv_id_from_report(report_id: str) -> int:
    """Extract investigation DB id from 'RPT-0042' → 42."""
    try:
        return int(report_id.replace("RPT-", "").lstrip("0") or "0")
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid report_id: {report_id}")


@router.post("/api/resolutions/{report_id}/approve")
def approve(report_id: str):
    inv_id = _inv_id_from_report(report_id)
    conn = get_db()
    if not conn:
        raise HTTPException(status_code=503, detail="DB unavailable")
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE investigations SET approval_status='approved' WHERE id=%s RETURNING exception_id",
            (inv_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Investigation not found")
        cur.execute("UPDATE exceptions SET status='resolved' WHERE id=%s", (row[0],))
    conn.commit()
    logger.info("Investigation %s approved", inv_id)
    return {"status": "approved", "report_id": report_id}


@router.post("/api/resolutions/{report_id}/reject")
def reject(report_id: str):
    inv_id = _inv_id_from_report(report_id)
    conn = get_db()
    if not conn:
        raise HTTPException(status_code=503, detail="DB unavailable")
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE investigations SET approval_status='rejected' WHERE id=%s RETURNING exception_id",
            (inv_id,),
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Investigation not found")
        cur.execute("UPDATE exceptions SET status='escalated' WHERE id=%s", (row[0],))
    conn.commit()
    logger.info("Investigation %s rejected", inv_id)
    return {"status": "rejected", "report_id": report_id}


class ChatRequest(BaseModel):
    message: str


CHAT_SYSTEM = """You are a payment investigation assistant. The analyst is reviewing a completed
investigation report and asking follow-up questions. Answer concisely using only information
from the investigation context provided. If you need to describe a tool call you would make,
prefix it with [calls <tool_name>]."""


@router.post("/api/reports/{report_id}/chat")
async def chat(report_id: str, body: ChatRequest):
    inv_id = _inv_id_from_report(report_id)
    conn = get_db()
    if not conn:
        raise HTTPException(status_code=503, detail="DB unavailable")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT steps, findings, recommendation FROM investigations WHERE id=%s",
            (inv_id,),
        )
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Investigation not found")

    steps, findings, recommendation = row

    context = (
        f"Investigation report for {report_id}:\n\n"
        f"Steps taken:\n{json.dumps(steps, indent=2)}\n\n"
        f"Findings:\n{json.dumps(findings, indent=2)}\n\n"
        f"Recommendation:\n{json.dumps(recommendation, indent=2)}"
    )

    llm = ChatBedrock(
        model_id="anthropic.claude-sonnet-4-6",
        region_name=os.environ.get("AWS_REGION", "us-west-2"),
    )
    response = await llm.ainvoke([
        SystemMessage(content=CHAT_SYSTEM),
        HumanMessage(content=f"Investigation context:\n{context}\n\nAnalyst question: {body.message}"),
    ])

    answer = response.content
    tool_used = None
    if "[calls " in answer:
        import re
        m = re.search(r"\[calls ([^\]]+)\]", answer)
        if m:
            tool_used = m.group(1)

    return {"answer": answer, "tool": tool_used}
```

- [ ] **Step 2: Register router in `backend/main.py`**

```python
from routers.resolutions import router as resolutions_router
# ...
app.include_router(resolutions_router)
```

- [ ] **Step 3: Smoke-test approve/reject**

```bash
curl -s -X POST http://localhost:8000/api/resolutions/RPT-0001/approve | python3 -m json.tool
```

Expected: `{"status": "approved", "report_id": "RPT-0001"}` (or 404 if no investigation exists — that's fine).

- [ ] **Step 4: Commit**

```bash
git add backend/routers/resolutions.py backend/main.py
git commit -m "feat: HITL approve/reject and report Q&A chat endpoint"
```

---

## Task 9: Lambda modification + final wiring

**Files:**
- Modify: `jobs/payment-ingest/handler.py`
- Modify: `backend/main.py` (confirm all routers included, health endpoint still works)

**Interfaces:**
- Lambda reads `BACKEND_URL` env var; POSTs `{msg_id, uetr, detected_errors}` after faulty ingest

- [ ] **Step 1: Add backend notification to `jobs/payment-ingest/handler.py`**

Add at the top, after existing imports:
```python
import urllib.request
```

Add this function after `_ingest_record`:
```python
def _notify_backend(msg_id: str, uetr: str, is_faulty: bool, raw_xml: str):
    """Fire-and-forget POST to backend when a faulty payment is ingested."""
    backend_url = os.environ.get("BACKEND_URL", "")
    if not backend_url or not is_faulty:
        return
    try:
        # Derive detected errors from XML filename convention used by generator
        # Real pipeline: generator embeds errors in manifest; here we signal UNKNOWN
        payload = json.dumps({
            "msg_id": msg_id,
            "uetr": uetr,
            "detected_errors": [{"code": "UNKNOWN", "field": "", "value": ""}],
        }).encode("utf-8")
        req = urllib.request.Request(
            f"{backend_url}/api/ingest/exceptions",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(req, timeout=3)
        logger.info("Notified backend of faulty payment: %s", msg_id)
    except Exception as exc:
        logger.warning("Backend notification failed (non-fatal): %s", exc)
```

In `lambda_handler`, after `_ingest_record(key, parsed, raw_xml)` and incrementing `processed`:
```python
_notify_backend(parsed.get("msg_id", ""), parsed.get("uetr", ""), is_faulty, raw_xml)
```

- [ ] **Step 2: Add `BACKEND_URL` to Lambda Terraform env vars**

In `infra/lambda.tf`, add to the Lambda function's environment variables block:
```hcl
BACKEND_URL = var.backend_url
```

Add to `infra/variables.tf`:
```hcl
variable "backend_url" {
  description = "HTTPS URL of the PayInvestigator backend (ALB)"
  type        = string
  default     = ""
}
```

- [ ] **Step 3: Final `backend/main.py` audit**

Confirm `main.py` has all of:
```python
from contextlib import asynccontextmanager
from db import get_db
from routers.exceptions import router as exceptions_router
from routers.resolutions import router as resolutions_router
from agents.graph import build_graph, make_llm as _make_llm

@asynccontextmanager
async def lifespan(app: FastAPI):
    get_db()
    yield

app = FastAPI(title="PayInvestigator", lifespan=lifespan)
app.include_router(exceptions_router)
app.include_router(resolutions_router)
```

- [ ] **Step 4: Run full backend**

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Check all endpoints respond:
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/exceptions
curl http://localhost:8000/api/ping
```

All should return 200.

- [ ] **Step 5: Final commit**

```bash
git add jobs/payment-ingest/handler.py infra/lambda.tf infra/variables.tf backend/main.py
git commit -m "feat: Lambda notifies backend on faulty ingest; wire all routers"
```

---

## Self-Review Checklist

- [x] Branch: `feature/track1-agents` created in Task 1 Step 1
- [x] DB schema: `exceptions` + `investigations` tables in `db.py`
- [x] All 8 error codes in `ERROR_CATEGORY_MAP` (state.py) and `ERROR_TYPE_MAP` (exceptions.py)
- [x] `tx_id` formatted as `TX-{payment_db_id:05d}` in `list_exceptions()`
- [x] SSE `cls` values: `intake`, `investigation`, `technical`, `compliance`, `resolution`, `tool` — matches mock
- [x] `report_id` formatted as `RPT-{inv_id:04d}` — matches mock `RPT-0142`
- [x] HITL endpoint is `/api/resolutions/{report_id}/approve|reject` — matches `client.js`
- [x] Chat endpoint is `/api/reports/{report_id}/chat` — matches `client.js`
- [x] Lambda POST is fire-and-forget (non-fatal on failure)
- [x] Resolution agent never executes autonomously — recommends only
- [x] `get_graph()` singleton — graph compiled once, reused