import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

import boto3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import get_db, _ensure_schema
from pacs008_generator.generator import generate_batch
from routers.exceptions import router as exceptions_router
from routers.resolutions import router as resolutions_router

logger = logging.getLogger(__name__)

S3_BUCKET = os.environ.get("S3_BUCKET", "")


def _write_events(conn, messages):
    """Bulk-upsert all events from the manifest messages list."""
    rows = []
    for msg in messages:
        for evt in msg.get("events", []):
            rows.append({
                **evt,
                "msg_id": msg["msg_id"],
                "uetr": msg["uetr"],
            })
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    get_db()  # opens connection + runs _ensure_schema if DATABASE_URL is set
    yield


from agents.graph import build_graph, make_llm as _make_llm

_llm = None
_investigation_graph = None


def get_graph():
    global _llm, _investigation_graph
    if _investigation_graph is None:
        _llm = _make_llm()
        _investigation_graph = build_graph(_llm)
    return _investigation_graph


app = FastAPI(title="PayInvestigator", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(exceptions_router)
app.include_router(resolutions_router)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/api/ping")
def ping():
    return {"message": "pong"}


# ── Pacs.008 generation ────────────────────────────────────────────────────────

class SeedRequest(BaseModel):
    count: int = 10
    error_rate: float = 0.3
    seed: Optional[int] = None
    error_codes: Optional[list[str]] = None
    stuck_rate: float = 0.0


@app.post("/api/seed")
def seed(req: SeedRequest):
    if not S3_BUCKET:
        raise HTTPException(status_code=500, detail="S3_BUCKET env var not set")

    manifest = generate_batch(
        count=req.count,
        error_rate=req.error_rate,
        seed=req.seed,
        error_codes=req.error_codes or None,
        write_files=False,
        stuck_rate=req.stuck_rate,
    )

    s3 = boto3.client("s3")
    run_id = manifest["run_id"]
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    prefix = f"payments/{ts}-{run_id}/"

    uploaded = []
    for msg in manifest["messages"]:
        key = prefix + msg["file"]
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=msg["xml"].encode("utf-8"),
            ContentType="application/xml",
        )
        uploaded.append({
            "file": msg["file"],
            "s3_key": key,
            "uetr": msg["uetr"],
            "is_faulty": msg["is_faulty"],
            "is_stuck": msg.get("is_stuck", False),
            "errors": msg["errors"],
            "events": msg.get("events", []),
        })

    conn = get_db()
    events_written = 0
    if conn:
        try:
            _write_events(conn, manifest["messages"])
            events_written = sum(len(m.get("events", [])) for m in manifest["messages"])
        except Exception as exc:
            logger.warning("Event write failed (non-fatal): %s", exc)

    return {
        "run_id": run_id,
        "count": len(uploaded),
        "faulty": sum(1 for m in uploaded if m["is_faulty"]),
        "stuck": sum(1 for m in uploaded if m["is_stuck"]),
        "events_written": events_written,
        "s3_prefix": f"s3://{S3_BUCKET}/{prefix}",
        "messages": uploaded,
    }
