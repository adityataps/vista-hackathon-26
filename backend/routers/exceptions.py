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
