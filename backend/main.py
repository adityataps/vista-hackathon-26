import os
from datetime import datetime, timezone
from typing import Optional

import boto3
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from pacs008_generator.generator import generate_batch

S3_BUCKET = os.environ.get("S3_BUCKET", "")

app = FastAPI(title="PayInvestigator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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
            "is_faulty": msg["is_faulty"],
            "errors": msg["errors"],
        })

    return {
        "run_id": run_id,
        "count": len(uploaded),
        "faulty": sum(1 for m in uploaded if m["is_faulty"]),
        "s3_prefix": f"s3://{S3_BUCKET}/{prefix}",
        "messages": uploaded,
    }
